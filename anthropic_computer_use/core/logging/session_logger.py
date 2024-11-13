import os
import logging
from logging.handlers import RotatingFileHandler

class SessionLogger:
    def __init__(self, session_id: str, sessions_dir: str):
        self.session_id = session_id
        self.sessions_dir = sessions_dir
        self.logger = self._setup_logging()

        # Initialize token counters
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def _setup_logging(self) -> logging.Logger:
        """Configure logging for the session"""
        log_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(prefix)s - %(message)s"
        )
        log_file = os.path.join(self.sessions_dir, f"{self.session_id}.log")

        file_handler = RotatingFileHandler(
            log_file, maxBytes=1024 * 1024, backupCount=5
        )
        file_handler.setFormatter(log_formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)

        logger = logging.getLogger(self.session_id)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.setLevel(logging.DEBUG)

        return logger

    def update_token_usage(self, input_tokens: int, output_tokens: int):
        """Update the total token usage."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def log_total_cost(self):
        """Calculate and log the total cost based on token usage."""
        cost_per_million_input_tokens = 3.0  # $3.00 per million input tokens
        cost_per_million_output_tokens = 15.0  # $15.00 per million output tokens

        total_input_cost = (
            self.total_input_tokens / 1_000_000
        ) * cost_per_million_input_tokens
        total_output_cost = (
            self.total_output_tokens / 1_000_000
        ) * cost_per_million_output_tokens
        total_cost = total_input_cost + total_output_cost

        prefix = "📊 session"
        self.logger.info(
            f"Total input tokens: {self.total_input_tokens}", extra={"prefix": prefix}
        )
        self.logger.info(
            f"Total output tokens: {self.total_output_tokens}", extra={"prefix": prefix}
        )
        self.logger.info(
            f"Total input cost: ${total_input_cost:.6f}", extra={"prefix": prefix}
        )
        self.logger.info(
            f"Total output cost: ${total_output_cost:.6f}", extra={"prefix": prefix}
        )
        self.logger.info(f"Total cost: ${total_cost:.6f}", extra={"prefix": prefix})
