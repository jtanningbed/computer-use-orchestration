import os
import argparse
import sys
from .config import Config
from .orchestrator import Orchestrator

# Initialize configuration
config = Config()

EDITOR_DIR = os.path.join(os.getcwd(), config.get("editor", "base_dir"))
SESSIONS_DIR = os.path.join(os.getcwd(), config.get("logging", "log_dir"))
os.makedirs(SESSIONS_DIR, exist_ok=True)

# Get system prompts from config
BASH_SYSTEM_PROMPT = config.get("bash", "system_prompt")
EDITOR_SYSTEM_PROMPT = config.get("editor", "system_prompt")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", help="The prompt for Claude", nargs="?")
    parser.add_argument("--config", help="Path to custom configuration file",
                       default="config.yaml")
    parser.add_argument("--session", help="Continue existing session")
    parser.add_argument(
        "--no-agi",
        action="store_true",
        help="When set, commands will not be executed",
    )
    args = parser.parse_args()

    try:
        # Initialize config once
        config = Config(args.config)
        
        # Create directories
        os.makedirs(config.get("logging", "log_dir"), exist_ok=True)
        os.makedirs(config.get("editor", "base_dir"), exist_ok=True)
        os.makedirs(config.get("mermaid", "output_dir"), exist_ok=True)

        # Create orchestrator with config
        orchestrator = Orchestrator(session_id=args.session, config=config)
        print(f"Session ID: {orchestrator.session_id}")
        
        # Process the request
        orchestrator.process_request(args.prompt)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
