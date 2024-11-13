from typing import Any, Optional
import os
import json
import logging
import anthropic
from datetime import datetime
import uuid
from .config import Config
from .core.logging import SessionLogger
from .sessions import (
    EditorSession, 
    BashSession,
    MermaidSession, 
    DBSession
)

class Orchestrator:
    """Orchestrates interactions between different tools based on user input"""

    def __init__(self, session_id: Optional[str] = None, config: Optional[Config] = None):
        self.session_id = session_id or self._create_session_id()
        self.config = config or Config()
        self.sessions_dir = os.path.join(os.getcwd(), self.config.get("logging", "log_dir"))
        os.makedirs(self.sessions_dir, exist_ok=True)
        self.client = anthropic.Anthropic()

        # Initialize session logger
        self.session_logger = SessionLogger(self.session_id, self.sessions_dir)
        self.logger = logging.LoggerAdapter(
            self.session_logger.logger, {"prefix": "🎭 orchestrator"}
        )

        # Initialize tool sessions
        self.editor = EditorSession(self.session_id, self.config)
        self.bash = BashSession(self.session_id, self.config)
        self.mermaid = MermaidSession(self.session_id, self.config)
        self.db = DBSession(self.session_id, self.config)

        # Set loggers for all sessions
        self.editor.set_logger(self.session_logger)
        self.bash.set_logger(self.session_logger)
        self.mermaid.set_logger(self.session_logger)
        self.db.set_logger(self.session_logger)

    def _create_session_id(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{timestamp}-{uuid.uuid4().hex[:6]}"

    def analyze_task(self, user_input: str) -> dict[str, Any]:
        """Analyze user input to determine required tools and actions"""

        try:
            response = self.client.beta.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=[{
                    "role": "user", 
                    "content": f"Analyze this request and determine which tools are needed: {user_input}"
                }],
                system="""You are a task analyzer that determines which tools are needed and how to break down a request.
                Available tools and their capabilities:

                - editor: Code and file editing operations
                - bash: System commands and file operations  
                - mermaid: Creating and editing diagrams
                - database: SQL queries and database operations (handles all schema validation internally)

                Break down complex tasks into subtasks for each tool. For example:
                - If a task requires querying data then saving to a file, split into:
                  1. database subtask: "Get the required data" (the database agent will handle schema details)
                  2. editor subtask: "Save the query results to file X"

                Let each tool handle its domain expertise - don't try to specify implementation details.

                Respond with ONLY a JSON object in this exact format:
                {
                    "primary_tool": "tool_name",
                    "primary_input": "high-level instructions for primary tool",
                    "secondary_tools": [],
                    "secondary_inputs": [],
                    "task_type": "string",
                    "suggested_approach": "string"
                }""",
            )

            analysis = json.loads(response.content[0].text)
            self.logger.info(f"Task analysis: {analysis}")
            return analysis

        except Exception as e:
            self.logger.error(f"Error analyzing task: {e}")
            return {
                "primary_tool": "editor",
                "secondary_tools": [],
                "task_type": "unknown",
                "suggested_approach": "direct execution"
            }


    def execute_task(self, user_input: str, analysis: dict[str, Any]) -> None:
        """Execute task using appropriate tools based on analysis"""
        
        try:
            primary_tool = analysis.get("primary_tool", "editor")
            primary_input = analysis.get("primary_input", user_input)
            result = None

            # Log execution plan
            self.logger.info(f"Executing task with primary tool: {primary_tool}")
            self.logger.info(f"Primary tool input: {primary_input}")

            # Execute primary tool with its specific input
            if primary_tool == "editor":
                result = self.editor.process_edit(primary_input)
            elif primary_tool == "bash":
                result = self.bash.process_bash_command(primary_input)
            elif primary_tool == "mermaid":
                result = self.mermaid.process_mermaid_prompt(primary_input)
            elif primary_tool == "database":
                result = self.db.process_query(primary_input)
            else:
                raise ValueError(f"Unknown tool: {primary_tool}")

            # Log the result for debugging
            self.logger.info(f"{result=}")

            # Process secondary tools with their specific inputs
            if result and not result.get("is_error"):
                for tool, tool_input in zip(
                    analysis.get("secondary_tools", []),
                    analysis.get("secondary_inputs", [])
                ):
                    self.logger.info(f"Processing with secondary tool: {tool}")
                    if tool == "editor":
                        result = self.editor.process_edit(tool_input, result)
                    elif tool == "bash":
                        result = self.bash.process_bash_command(tool_input, result)
                    elif tool == "mermaid":
                        result = self.mermaid.process_mermaid_prompt(tool_input, result)
                    elif tool == "database":
                        result = self.db.process_query(tool_input, result)

        except Exception as e:
            self.logger.error(f"Error executing task: {e}")
            raise

    def process_request(self, user_input: str) -> None:
        """Main entry point for processing user requests"""

        try:
            self.logger.info(f"Processing request: {user_input}")

            # Analyze the task
            analysis = self.analyze_task(user_input)

            # Execute the task
            self.execute_task(user_input, analysis)

            # Log completion and costs
            self.session_logger.log_total_cost()

        except Exception as e:
            self.logger.error(f"Error processing request: {e}")
            raise
