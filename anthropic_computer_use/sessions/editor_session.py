import os
import anthropic
from typing import Any, Optional
from .base_session import BaseSession
from ..config import Config

class EditorSession(BaseSession):
    def __init__(self, session_id: Optional[str] = None, config: Optional[Config] = None):
        super().__init__(session_id, config)
        editor_config = self.config.get("editor")
        self.editor_dir = os.path.join(
            os.getcwd(), editor_config.get("base_dir")
        )
        self.log_prefix = "📝 file_editor"
        os.makedirs(self.editor_dir, exist_ok=True)

    def _get_editor_path(self, path: str) -> str:
        """Convert API path to local editor directory path"""
        # Strip any leading /repo/ from the path
        clean_path = path.replace("/repo/", "", 1)
        # Join with editor_dir
        full_path = os.path.join(self.editor_dir, clean_path)
        # Create the directory structure if it doesn't exist
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        return full_path

    def _handle_view(self, path: str, _: dict[str, Any]) -> dict[str, Any]:
        """Handle view command"""
        editor_path = self._get_editor_path(path)
        if os.path.exists(editor_path):
            with open(editor_path, "r") as f:
                return {"content": f.read()}
        return {"error": f"File {editor_path} does not exist"}

    def _handle_create(self, path: str, tool_call: dict[str, Any]) -> dict[str, Any]:
        """Handle create command"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(tool_call["file_text"])
        return {"content": f"File created at {path}"}

    def _handle_str_replace(
        self, path: str, tool_call: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle str_replace command"""
        with open(path, "r") as f:
            content = f.read()
        if tool_call["old_str"] not in content:
            return {"error": "old_str not found in file"}
        new_content = content.replace(
            tool_call["old_str"], tool_call.get("new_str", "")
        )
        with open(path, "w") as f:
            f.write(new_content)
        return {"content": "File updated successfully"}

    def _handle_insert(self, path: str, tool_call: dict[str, Any]) -> dict[str, Any]:
        """Handle insert command"""
        with open(path, "r") as f:
            lines = f.readlines()
        insert_line = tool_call["insert_line"]
        if insert_line > len(lines):
            return {"error": "insert_line beyond file length"}
        lines.insert(insert_line, tool_call["new_str"] + "\n")
        with open(path, "w") as f:
            f.writelines(lines)
        return {"content": "Content inserted successfully"}

    def handle_text_editor_tool(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """Handle text editor tool calls"""
        try:
            command = tool_call["command"]
            if not all(key in tool_call for key in ["command", "path"]):
                return {"error": "Missing required fields"}

            # Get path and ensure directory exists
            path = self._get_editor_path(tool_call["path"])

            handlers = {
                "view": self._handle_view,
                "create": self._handle_create,
                "str_replace": self._handle_str_replace,
                "insert": self._handle_insert,
            }

            handler = handlers.get(command)
            if not handler:
                return {"error": f"Unknown command {command}"}

            return handler(path, tool_call)

        except Exception as e:
            self.logger.error(f"Error in handle_text_editor_tool: {str(e)}")
            return {"error": str(e)}

    def process_tool_calls(
        self, tool_calls: list[anthropic.types.ContentBlock]
    ) -> list[dict[str, Any]]:
        """Process tool calls and return results"""
        results = []

        for tool_call in tool_calls:
            if tool_call.type == "tool_use" and tool_call.name == "str_replace_editor":

                # Log the keys and first 20 characters of the values of the tool_call
                for key, value in tool_call.input.items():
                    truncated_value = str(value)[:20] + (
                        "..." if len(str(value)) > 20 else ""
                    )
                    self.logger.info(
                        f"Tool call key: {key}, Value (truncated): {truncated_value}"
                    )

                result = self.handle_text_editor_tool(tool_call.input)
                # Convert result to match expected tool result format
                is_error = False

                if result.get("error"):
                    is_error = True
                    tool_result_content = [{"type": "text", "text": result["error"]}]
                else:
                    tool_result_content = [
                        {"type": "text", "text": result.get("content", "")}
                    ]

                results.append(
                    {
                        "tool_call_id": tool_call.id,
                        "output": {
                            "type": "tool_result",
                            "content": tool_result_content,
                            "tool_use_id": tool_call.id,
                            "is_error": is_error,
                        },
                    }
                )

        return results

    def process_edit(self, edit_prompt: str, previous_result: Optional[Any] = None) -> Optional[Any]:
        """Main method to process editing prompts"""
        tools = [{"type": "text_editor_20241022", "name": "str_replace_editor"}]
        return self._process_messages(
            edit_prompt, 
            tools, 
            self.config.get("editor", "system_prompt"),
            previous_result
        )
