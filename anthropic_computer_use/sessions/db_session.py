from datetime import datetime, date, time
import json
from typing import Any, Optional, Tuple
from decimal import Decimal
from json import JSONEncoder
import anthropic
from .base_session import BaseSession
from ..core.database import PostgresEngine
from ..config import Config


class DatabaseJSONEncoder(JSONEncoder):
    """Custom JSON encoder to handle database-specific types"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, time):
            return obj.isoformat()
        return super().default(obj)


class DBSession(BaseSession):
    """Database session manager"""

    def __init__(self, session_id: Optional[str] = None, config: Optional[Config] = None):
        """Initialize database session"""
        super().__init__(session_id, config)
        self.log_prefix = "🗄️ database"
        
        # Check if database is enabled
        self.enabled = self.config.get("database", {}).get("enabled", False)
        self.engine = None
        
        if self.enabled:
            # Initialize database engine using config
            db_config = self.config.get("database")
            try:
                self.engine = self._initialize_engine(db_config)
            except Exception as e:
                self.logger.error(f"Failed to initialize database: {e}")
                self.enabled = False
                self.engine = None

    def _check_enabled(self) -> None:
        """Check if database functionality is enabled"""
        if not self.enabled:
            raise RuntimeError(
                "Database functionality is not enabled. "
                "Please configure database settings in .env file."
            )

    def _initialize_engine(self, db_config: dict) -> PostgresEngine:
        """Initialize and connect database engine"""
        try:
            engine = PostgresEngine(
                host=db_config.get("host"),
                database=db_config.get("database"),
                user=db_config.get("user"),
                password=db_config.get("password")
            )
            engine.connect()
            return engine
        except Exception as e:
            raise ConnectionError(f"Failed to initialize database session: {str(e)}")

    def execute_query(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Execute a database query with logging"""
        self._check_enabled()
        try:
            self.logger.info(f"Executing query: {query}")
            result = self.engine.execute(query, params)
            self.logger.info("Query executed successfully")
            return result
        except Exception as e:
            self.logger.error(f"Query execution failed: {str(e)}")
            raise

    def fetch_all_results(self, query: str, params: Optional[Tuple] = None) -> list[dict[str, Any]]:
        """Fetch all results with logging"""
        try:
            self.logger.info(f"Fetching all results for query: {query}")
            results = self.engine.fetch_all(query, params)
            self.logger.info(f"Fetched {len(results)} results")
            return results
        except Exception as e:
            self.logger.error(f"Failed to fetch results: {str(e)}")
            raise

    def fetch_one_result(self, query: str, params: Optional[Tuple] = None) -> Optional[dict[str, Any]]:
        """Fetch single result with logging"""
        try:
            self.logger.info(f"Fetching one result for query: {query}")
            result = self.engine.fetch_one(query, params)
            self.logger.info("Result fetched successfully")
            return result
        except Exception as e:
            self.logger.error(f"Failed to fetch result: {str(e)}")
            raise

    def get_tables(self) -> list[str]:
        """Get list of all tables in the database"""
        query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """
        try:
            results = self.engine.fetch_all(query)
            return [row['table_name'] for row in results]
        except Exception as e:
            self.logger.error(f"Failed to get tables: {str(e)}")
            raise

    def get_table_schema(self, table_name: str) -> list[dict[str, Any]]:
        """Get schema information for a specific table"""
        query = """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
        """
        try:
            return self.engine.fetch_all(query, (table_name,))
        except Exception as e:
            self.logger.error(f"Failed to get schema for table {table_name}: {str(e)}")
            raise

    def get_table_constraints(self, table_name: str) -> list[dict[str, Any]]:
        """Get constraints for a specific table"""
        query = """
            SELECT c.conname as constraint_name,
                   c.contype as constraint_type,
                   pg_get_constraintdef(c.oid) as definition
            FROM pg_constraint c
            JOIN pg_namespace n ON n.oid = c.connamespace
            JOIN pg_class t ON t.oid = c.conrelid
            WHERE t.relname = %s AND n.nspname = 'public'
        """
        try:
            return self.engine.fetch_all(query, (table_name,))
        except Exception as e:
            self.logger.error(f"Failed to get constraints for table {table_name}: {str(e)}")
            raise

    def get_table_indexes(self, table_name: str) -> list[dict[str, Any]]:
        """Get indexes for a specific table"""
        query = """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = %s AND schemaname = 'public'
        """
        try:
            return self.engine.fetch_all(query, (table_name,))
        except Exception as e:
            self.logger.error(f"Failed to get indexes for table {table_name}: {str(e)}")
            raise

    def _handle_operation(self, operation: str, tool_call: dict[str, Any]) -> Any:
        """Handle different database operations with error recovery"""
        try:
            return self._execute_operation(operation, tool_call)
        except Exception as e:
            # Log the initial error
            self.logger.error(f"Initial error in operation {operation}: {str(e)}")
            
            try:
                # Attempt to diagnose the issue
                error_info = self._diagnose_error(str(e), operation, tool_call)
                
                if error_info.get("recoverable"):
                    # Try to recover based on the diagnosis
                    return self._attempt_recovery(error_info, operation, tool_call)
                else:
                    # If not recoverable, return detailed error information
                    return {
                        "error": str(e),
                        "diagnosis": error_info.get("diagnosis"),
                        "suggested_fix": error_info.get("suggestion")
                    }
                    
            except Exception as recovery_error:
                self.logger.error(f"Error during recovery attempt: {str(recovery_error)}")
                return {"error": f"Original error: {str(e)}\nRecovery failed: {str(recovery_error)}"}

    def _execute_operation(self, operation: str, tool_call: dict[str, Any]) -> Any:
        """Execute the database operation"""
        if operation == "query":
            return self.engine.fetch_all(tool_call.get("query"))
        elif operation == "list_tables":
            return self.get_tables()
        elif operation == "inspect_table":
            table_name = tool_call.get("table_name")
            return {
                "schema": self.get_table_schema(table_name),
                "constraints": self.get_table_constraints(table_name),
                "indexes": self.get_table_indexes(table_name)
            }
        elif operation == "get_schema":
            tables = self.get_tables()
            return {table: {
                "schema": self.get_table_schema(table),
                "constraints": self.get_table_constraints(table),
                "indexes": self.get_table_indexes(table)
            } for table in tables}
        else:
            raise ValueError(f"Unknown operation: {operation}")

    def process_tool_calls(
        self, tool_calls: list[anthropic.types.ContentBlock]
    ) -> list[dict[str, Any]]:
        """Process database tool calls with enhanced error handling"""
        if not self.enabled:
            return [{
                "tool_call_id": tool_call.id,
                "output": {
                    "type": "tool_result",
                    "content": [{
                        "type": "text",
                        "text": "Database functionality is not enabled. Please configure database settings in .env file."
                    }],
                    "tool_use_id": tool_call.id,
                    "is_error": True,
                    "is_recoverable": False
                }
            } for tool_call in tool_calls if tool_call.type == "tool_use" and tool_call.name == "database"]

        results = []
        for tool_call in tool_calls:
            if tool_call.type == "tool_use" and tool_call.name == "database":
                self.logger.info(f"Database tool call input: {tool_call.input}")
                
                try:
                    operation = tool_call.input.get("operation")
                    result = self._handle_operation(operation, tool_call.input)

                    # Check if we got an error with recovery information
                    if isinstance(result, dict) and "recovery_info" in result:
                        # Add recovery information to the messages for the agent to process
                        recovery_message = {
                            "role": "system",
                            "content": [{
                                "type": "text",
                                "text": f"Error occurred but recovery information is available:\n{json.dumps(result['recovery_info'], indent=2)}"
                            }]
                        }
                        self.messages.append(recovery_message)
                        
                        # Return the recovery information to allow the agent to retry
                        results.append({
                            "tool_call_id": tool_call.id,
                            "output": {
                                "type": "tool_result",
                                "content": [{
                                    "type": "text",
                                    "text": json.dumps({
                                        "error": True,
                                        "recovery_info": result["recovery_info"]
                                    })
                                }],
                                "tool_use_id": tool_call.id,
                                "is_error": True,
                                "is_recoverable": True
                            }
                        })
                        continue

                    # Get the analysis text from the most recent message content
                    analysis_text = None
                    for msg in self.messages:
                        if msg.get("role") == "assistant" and msg.get("content"):
                            for content in msg["content"]:
                                if content.get("type") == "text":
                                    analysis_text = content.get("text")

                    # Create a combined result with both analysis and raw data
                    combined_result = {
                        "analysis": analysis_text,
                        "data": result
                    }

                    results.append({
                        "tool_call_id": tool_call.id,
                        "output": {
                            "type": "tool_result",
                            "content": [{
                                "type": "text", 
                                "text": json.dumps(combined_result, cls=DatabaseJSONEncoder)
                            }],
                            "tool_use_id": tool_call.id,
                            "is_error": False
                        }
                    })

                except Exception as e:
                    self.logger.error(f"Error processing tool call: {str(e)}")
                    results.append({
                        "tool_call_id": tool_call.id,
                        "output": {
                            "type": "tool_result",
                            "content": [{"type": "text", "text": str(e)}],
                            "tool_use_id": tool_call.id,
                            "is_error": True,
                            "is_recoverable": False
                        }
                    })

        return results

    def process_query(self, user_input: str, previous_result: Optional[Any] = None) -> Optional[Any]:
        """Process database queries and schema inspection requests"""
        tools = [{
            "name": "database", 
            "description": "Execute database operations including queries and schema inspection",
            "input_schema": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": [
                            "query",
                            "list_tables", 
                            "inspect_table",
                            "get_schema",
                        ],
                        "description": "Type of database operation to perform",
                    },
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute (for query operation)",
                    },
                    "table_name": {
                        "type": "string",
                        "description": "Table name for inspection operations",
                    },
                },
                "required": ["operation"],
            },
        }]
        
        return self._process_messages(
            user_input,
            tools,
            self.config.get("database", "system_prompt"),
            previous_result
        )

    def __del__(self):
        """Cleanup database connection"""
        if hasattr(self, 'engine'):
            self.engine.disconnect()
    def _diagnose_error(self, error_message: str, operation: str, tool_call: dict[str, Any]) -> dict[str, Any]:
        """Diagnose database errors and determine if they're recoverable"""
        diagnosis = {
            "recoverable": False,
            "diagnosis": "",
            "suggestion": "",
            "recovery_action": None
        }
        
        # Check for common error patterns
        if "relation" in error_message and "does not exist" in error_message:
            # Extract the table name from the error
            import re
            table_match = re.search(r'relation "(.*?)" does not exist', error_message)
            if table_match:
                table_name = table_match.group(1)
                
                # Get list of available tables
                available_tables = self.get_tables()
                
                # Find similar table names (using fuzzy matching)
                from difflib import get_close_matches
                similar_tables = get_close_matches(table_name, available_tables, n=3, cutoff=0.6)
                
                diagnosis.update({
                    "recoverable": True,
                    "diagnosis": f"Table '{table_name}' not found",
                    "suggestion": f"Similar tables: {', '.join(similar_tables)}" if similar_tables else "No similar tables found",
                    "recovery_action": "suggest_tables",
                    "similar_tables": similar_tables
                })
        
        elif "column" in error_message and "does not exist" in error_message:
            # Handle missing column errors
            table_name = tool_call.get("table_name", "")
            if table_name:
                schema = self.get_table_schema(table_name)
                available_columns = [col["column_name"] for col in schema]
                
                diagnosis.update({
                    "recoverable": True,
                    "diagnosis": f"Invalid column in table '{table_name}'",
                    "suggestion": f"Available columns: {', '.join(available_columns)}",
                    "recovery_action": "show_schema",
                    "schema": schema
                })
        
        elif "permission denied" in error_message.lower():
            diagnosis.update({
                "recoverable": False,
                "diagnosis": "Insufficient permissions",
                "suggestion": "Please check database user permissions"
            })
        
        return diagnosis

    def _attempt_recovery(self, error_info: dict[str, Any], operation: str, tool_call: dict[str, Any]) -> Any:
        """Attempt to recover from errors based on diagnosis"""
        recovery_action = error_info.get("recovery_action")
        
        if recovery_action == "suggest_tables":
            # Return information about similar tables and their schemas
            similar_tables = error_info.get("similar_tables", [])
            table_info = {}
            
            for table in similar_tables:
                try:
                    schema = self.get_table_schema(table)
                    sample_data = self.engine.fetch_one(f"SELECT * FROM {table} LIMIT 1")
                    table_info[table] = {
                        "schema": schema,
                        "sample_data": sample_data
                    }
                except Exception as e:
                    self.logger.error(f"Error getting info for table {table}: {str(e)}")
            
            return {
                "recovery_info": {
                    "type": "table_suggestions",
                    "similar_tables": table_info,
                    "original_error": error_info["diagnosis"],
                    "suggestion": error_info["suggestion"]
                }
            }
        
        elif recovery_action == "show_schema":
            # Return detailed schema information
            return {
                "recovery_info": {
                    "type": "schema_info",
                    "schema": error_info["schema"],
                    "original_error": error_info["diagnosis"],
                    "suggestion": error_info["suggestion"]
                }
            }
        
        return {"error": "Unable to recover from error", "diagnosis": error_info["diagnosis"]}
