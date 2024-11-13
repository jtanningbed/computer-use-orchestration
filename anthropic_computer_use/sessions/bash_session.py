import os
import subprocess
import anthropic
from typing import Any, Optional
import traceback
from .base_session import BaseSession
from ..config import Config

class BashSession(BaseSession):
    def __init__(self, session_id: Optional[str] = None, config: Optional[Config] = None, no_agi: bool = False):
        super().__init__(session_id, config)
        self.environment = os.environ.copy()
        self.log_prefix = "🐚 bash"
        self.no_agi = no_agi

    def _handle_bash_command(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """Handle bash command execution"""
        try:
            command = tool_call.get("command")
            restart = tool_call.get("restart", False)

            if restart:
                self.environment = os.environ.copy()  # Reset the environment
                self.logger.info("Bash session restarted.")
                return {"content": "Bash session restarted."}

            if not command:
                self.logger.error("No command provided to execute.")
                return {"error": "No command provided to execute."}

            # Check if no_agi is enabled
            if self.no_agi:
                self.logger.info(f"Mock executing bash command: {command}")
                return {"content": "in mock mode, command did not run"}

            # Log the command being executed
            self.logger.info(f"Executing bash command: {command}")

            # Execute the command in a subprocess
            result = subprocess.run(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.environment,
                text=True,
                executable="/bin/bash",
            )

            output = result.stdout.strip()
            error_output = result.stderr.strip()

            # Log the outputs
            if output:
                self.logger.info(
                    f"Command output:\n\n```output for '{command[:20]}...'\n{output}\n```"
                )
            if error_output:
                self.logger.error(
                    f"Command error output:\n\n```error for '{command}'\n{error_output}\n```"
                )

            if result.returncode != 0:
                error_message = error_output or "Command execution failed."
                return {"error": error_message}

            return {"content": output}

        except Exception as e:
            self.logger.error(f"Error in _handle_bash_command: {str(e)}")
            self.logger.error(traceback.format_exc())
            return {"error": str(e)}

    def process_tool_calls(
        self, tool_calls: list[anthropic.types.ContentBlock]
    ) -> list[dict[str, Any]]:
        """Process tool calls and return results"""
        results = []

        for tool_call in tool_calls:
            if tool_call.type == "tool_use" and tool_call.name == "bash":
                self.logger.info(f"Bash tool call input: {tool_call.input}")

                result = self._handle_bash_command(tool_call.input)

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

    def process_bash_command(self, bash_prompt: str,  previous_result: Optional[Any] = None) -> Optional[Any]:
        """Main method to process bash commands"""
        tools = [{"type": "bash_20241022", "name": "bash"}]
        self._process_messages(
            bash_prompt,
            tools,
            self.config.get("bash", "system_prompt"),
            previous_result,
        )
