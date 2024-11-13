import os
import base64
import io
import requests
import anthropic
from typing import Any, Optional
from PIL import Image, UnidentifiedImageError
from .base_session import BaseSession
from ..config import Config

class MermaidSession(BaseSession):
    def __init__(self, session_id: Optional[str] = None, config: Optional[Config] = None):
        super().__init__(session_id, config)
        self.output_dir = os.path.join(os.getcwd(), self.config.get("mermaid", "output_dir"))
        self.log_prefix = "📊 mermaid"

    def _handle_mermaid_tool(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """Handle mermaid diagram generation"""
        try:
            diagram = tool_call.get("diagram")
            if not diagram:
                return {"error": "No diagram content provided"}

            output_file = tool_call.get("output_file", "diagram.png")
            width = tool_call.get("width", 1200)  # Larger default width
            height = tool_call.get("height", 800)  # Larger default height

            # Ensure output directory exists
            os.makedirs(os.path.dirname(os.path.join(self.output_dir, output_file)), exist_ok=True)

            output_path = os.path.join(self.output_dir, output_file)

            img = self._generate_mermaid_diagram(diagram, output_path, width, height)

            if img:
                return {"content": f"Diagram generated successfully at {output_path}"}
            else:
                return {"error": "Failed to generate diagram. Please check the diagram syntax and try again."}

        except Exception as e:
            self.logger.error(f"Error in _handle_mermaid_tool: {str(e)}")
            return {"error": str(e)}

    def _generate_mermaid_diagram(self, diagram: str, output_file: str, width: int = 800, height: int = 600) -> Optional[Image.Image]:
        """Generate mermaid diagram using mermaid.ink"""
        try:
            # Log the diagram code for debugging
            self.logger.info(f"Generating diagram with code:\n{diagram}")

            # Encode the diagram
            graphbytes = diagram.encode("utf8")
            base64_bytes = base64.b64encode(graphbytes)
            base64_string = base64_bytes.decode("ascii")

            # Construct URL with error checking
            if not base64_string:
                self.logger.error("Failed to encode diagram")
                return None

            # Build URL with larger default size and lighter theme
            url = (
                "https://mermaid.ink/img/"
                + base64_string
                + f"?width={width}&height={height}&theme=default"
            )

            self.logger.info(f"Requesting diagram from URL: {url}")

            # Get the image with timeout
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Raise error for bad status codes

            # Try to open and validate the image
            try:
                img = Image.open(io.BytesIO(response.content))
                img.verify()  # Verify it's a valid image
                img = Image.open(io.BytesIO(response.content))  # Reopen after verify
                img.save(output_file)
                self.logger.info(f"Successfully saved diagram to {output_file}")
                return img
            except UnidentifiedImageError:
                self.logger.error("Failed to identify image - invalid diagram syntax")
                return None
            except Exception as e:
                self.logger.error(f"Error saving image: {str(e)}")
                return None

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error: {str(e)}")
            return None

    def process_tool_calls(
        self, tool_calls: list[anthropic.types.ContentBlock]
    ) -> list[dict[str, Any]]:
        """Process mermaid tool calls and return results"""
        results = []

        for tool_call in tool_calls:
            if tool_call.type == "tool_use" and tool_call.name == "mermaid":
                self.logger.info(f"Mermaid tool call input: {tool_call.input}")
                result = self._handle_mermaid_tool(tool_call.input)
                
                is_error = bool(result.get("error"))
                content = result.get("error") if is_error else result.get("content", "")
                
                results.append({
                    "tool_call_id": tool_call.id,
                    "output": {
                        "type": "tool_result",
                        "content": [{"type": "text", "text": content}],
                        "tool_use_id": tool_call.id,
                        "is_error": is_error,
                    }
                })

        return results

    def process_mermaid_prompt(self, mermaid_prompt: str, previous_result: Optional[Any] = None) -> Optional[Any]:
        """Main method to process mermaid diagram generation"""
        tools = [{
            "type": "custom",
            "name": "mermaid",
            "description": "Generate a Mermaid diagram. Use flowchart TD for top-down flowcharts. Keep node IDs simple and alphanumeric. Use quotes for labels with spaces. Avoid special characters.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "diagram": {
                        "type": "string",
                        "description": "The Mermaid diagram definition without backticks. Use simple node IDs."
                    },
                    "output_file": {
                        "type": "string",
                        "description": "Output filename (e.g. workflow.png)"
                    },
                    "width": {
                        "type": "integer",
                        "description": "Width in pixels",
                        "default": 1200
                    },
                    "height": {
                        "type": "integer",
                        "description": "Height in pixels",
                        "default": 800
                    }
                },
                "required": ["diagram"]
            }
        }]
        return self._process_messages(mermaid_prompt, tools, self.config.get("mermaid", "system_prompt"), previous_result)
