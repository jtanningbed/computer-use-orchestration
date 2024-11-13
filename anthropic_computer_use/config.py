import os
import yaml
from typing import Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Default configuration with optional database config
DEFAULT_CONFIG = {
    "editor": {
        "base_dir": os.getenv("EDITOR_DIR", "editor_dir"),
        "system_prompt": """
            You are a helpful assistant that helps users edit text files.
            When receiving results from other tools, you can use that data to create or modify files.
            If you receive database query results, you can save them to files or process them as needed.
        """,
        "max_tokens": 8192,
        "model": "claude-3-5-sonnet-20241022"
    },
    
    "mermaid": {
        "output_dir": "output/diagrams",
        "default_width": 1200,
        "default_height": 800,
        "theme": "default",
        "system_prompt": """
            You are an expert at creating Mermaid diagrams. 
            Help users create clear and effective diagrams based on their requirements.
        """
    },
    
    "bash": {
        "allowed_commands": ["git", "ls", "cat", "grep"],
        "restricted_paths": [],
        "no_agi_mode": False,
        "system_prompt": "You are a helpful assistant that can execute bash commands."
    },
    
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(prefix)s - %(message)s",
        "retention": 5,
        "max_size_mb": 1,
        "log_dir": os.getenv("LOG_DIR", ".session_logs")
    },
    
    "database": {
        "enabled": bool(os.getenv("DB_HOST")),  # Only enable if host is configured
        "default_engine": "postgres",
        "connection_timeout": 30,
        "max_connections": 5,
        "enable_ssl": False,
        "host": os.getenv("DB_HOST"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME"),
        "system_prompt": """
            You are a database expert that helps users interact with databases safely and efficiently.
            
            When you encounter errors:
            1. Review any recovery information provided
            2. Adjust your approach based on suggested tables or schemas
            3. Try alternative queries if the original fails
            4. Explain what went wrong and how you're adjusting

            If you receive recovery information about similar tables or schemas:
            1. Examine the suggested alternatives
            2. Verify if they contain the required information
            3. Modify your query to use the correct table/columns
            4. Explain the adjustment to the user

            Always validate inputs and use parameterized queries to prevent SQL injection.
            Explain your reasoning when constructing complex queries.
        """
    }
}

class Config:
    def __init__(self, config_path: str = None):
        """Initialize configuration with optional custom config file"""
        self.config = DEFAULT_CONFIG.copy()
        
        # Load custom config if provided
        if config_path and os.path.exists(config_path):
            self._load_custom_config(config_path)
        
        # Validate required environment variables
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate that all required configuration values are present"""
        # Only ANTHROPIC_API_KEY is required
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError(
                "Missing required environment variable: ANTHROPIC_API_KEY\n" +
                "Please set this in your .env file or environment."
            )
        
        # Validate database config only if enabled
        if self.config["database"]["enabled"]:
            required_db_vars = {
                "DB_USER": "Database username",
                "DB_PASSWORD": "Database password",
                "DB_NAME": "Database name"
            }
            
            missing_vars = []
            for var, description in required_db_vars.items():
                if not os.getenv(var):
                    missing_vars.append(f"{description} ({var})")
            
            if missing_vars:
                self.config["database"]["enabled"] = False
                print(
                    "Warning: Database functionality disabled due to missing configuration:\n" +
                    "\n".join(f"- {var}" for var in missing_vars)
                )

    def _load_custom_config(self, config_path: str) -> None:
        """Load and merge custom configuration from yaml file"""
        try:
            with open(config_path, 'r') as f:
                custom_config = yaml.safe_load(f)
                if custom_config:
                    self._merge_config(custom_config)
        except Exception as e:
            print(f"Error loading custom config: {str(e)}")

    def _merge_config(self, custom_config: dict[str, Any]) -> None:
        """Deep merge custom config with default config"""
        for key, value in custom_config.items():
            if key in self.config and isinstance(self.config[key], dict):
                self.config[key].update(value)
            else:
                self.config[key] = value

    def get(self, section: str, key: str = None) -> Any:
        """Get configuration value(s)"""
        if key:
            value = self.config.get(section, {}).get(key)
            return value
        section_value = self.config.get(section, {})
        return section_value
