import os
import json
import logging
import traceback
from datetime import datetime
import uuid
from typing import Optional, Any
import anthropic
from abc import ABC, abstractmethod
from ..config import Config
from ..core.logging import SessionLogger

class BaseSession(ABC):
    """Base class for all session types"""
    
    def __init__(self, session_id: Optional[str] = None, config: Optional[Config] = None):
        """Initialize base session with optional existing session ID and config"""
        self.config = config or Config()  # Initialize config first
        self.session_id = session_id or self._create_session_id()
        self.sessions_dir = os.path.join(os.getcwd(), self.config.get("logging", "log_dir"))
        self.client = anthropic.Anthropic()
        self.messages = []
        self.logger = None
        self.log_prefix = "🔷 base"  # Should be overridden by subclasses

    def set_logger(self, session_logger: "SessionLogger") -> None:
        """Set the logger for the session"""
        self.session_logger = session_logger
        self.logger = logging.LoggerAdapter(
            self.session_logger.logger,
            {"prefix": self.log_prefix}
        )

    def _create_session_id(self) -> str:
        """Create a new session ID"""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{timestamp}-{uuid.uuid4().hex[:6]}"

    @abstractmethod
    def process_tool_calls(
        self, tool_calls: list[anthropic.types.ContentBlock]
    ) -> list[dict[str, Any]]:
        """Process tool calls and return results"""
        pass

    def _process_messages(self, user_input: str, tools: list[dict[str, Any]], system_prompt: str, previous_result: Optional[Any] = None) -> dict[str, Any]:
        """Common message processing logic"""
        try:
            # Create message content that includes previous result if available
            message_content = [{"type": "text", "text": user_input}]
            if previous_result:
                print(f"got previous result: {previous_result}")
                message_content.append({
                    "type": "text", 
                    "text": f"\nPrevious tool result: {json.dumps(previous_result)}"
                })

            # Initial message with proper content structure
            api_message = {
                "role": "user",
                "content": message_content
            }
            self.messages = [api_message]

            self.logger.info(f"User input: {api_message}")
            
            final_result = {
                "complete": False,  # Default to incomplete
                "content": None,
                "is_error": False
            }

            while True:
                response = self.client.beta.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=4096,
                    messages=self.messages,
                    tools=tools,
                    system=system_prompt,
                    betas=["computer-use-2024-10-22"],
                )

                # Extract token usage from the response
                input_tokens = getattr(response.usage, "input_tokens", 0)
                output_tokens = getattr(response.usage, "output_tokens", 0)
                self.logger.info(
                    f"API usage: input_tokens={input_tokens}, output_tokens={output_tokens}"
                )

                # Update token counts in SessionLogger
                self.session_logger.update_token_usage(input_tokens, output_tokens)

                self.logger.info(f"API response: {response.model_dump()}")

                # Convert response content to message params
                response_content = []
                for block in response.content:
                    if block.type == "text":
                        response_content.append({"type": "text", "text": block.text})
                    else:
                        response_content.append(block.model_dump())

                # Add assistant response to messages
                self.messages.append({"role": "assistant", "content": response_content})

                if response.stop_reason != "tool_use":
                    # Check if the response indicates completion
                    if any(marker in response.content[0].text.lower() for marker in ["task complete", "finished", "done"]):
                        final_result["complete"] = True
                    print(response.content[0].text)
                    break

                tool_results = self.process_tool_calls(response.content)
                
                if tool_results:
                    final_result["content"] = tool_results[0]["output"]
                    final_result["is_error"] = tool_results[0]["output"]["is_error"]

                    # Add tool results as user message
                    self.messages.append(
                        {"role": "user", "content": [tool_results[0]["output"]]}
                    )

                    if tool_results[0]["output"]["is_error"]:
                        self.logger.error(
                            f"Error: {tool_results[0]['output']['content']}"
                        )
                        break

            return final_result

        except Exception as e:
            self.logger.error(f"Error in process_messages: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise
