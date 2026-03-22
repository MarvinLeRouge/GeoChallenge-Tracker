"""Configuration of the centralized logging system."""

import glob
import json
import logging
import logging.handlers
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from bson import ObjectId


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle ObjectId and datetime."""

    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class DataLogger:
    """Specialized logger for heavy JSON data payloads."""

    def __init__(self, logs_dir: str = "logs"):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)

    def log_data(
        self, calling_context: str, data: dict[str, Any], user_data: Optional[dict[str, Any]] = None
    ) -> None:
        """Logs heavy data payloads as JSON."""
        today = datetime.now().strftime("%Y-%m-%d")
        json_file = self.logs_dir / f"{today}-data.json"

        entry = {
            "datetime": datetime.now().isoformat(),
            "calling_context": calling_context,
            "user_data": user_data or {},
            "data": data,
        }

        # Maintain a valid JSON file in array format
        if json_file.exists():
            # Read existing content and remove the trailing closing bracket
            with open(json_file, encoding="utf-8") as f:
                content = f.read()

            # Strip trailing whitespace and the last closing bracket
            content = content.rstrip()
            if content.endswith("]"):
                content = content[:-1]  # Remove ']'
                # Add a comma if this is not the first entry
                if content.rstrip().endswith("}"):
                    content += ","
            elif content.endswith("}"):
                content += ","

            # Rewrite the file with the new entry appended
            with open(json_file, "w", encoding="utf-8") as f:
                f.write(content)
                f.write(json.dumps(entry, cls=CustomJSONEncoder))
                f.write("]")
        else:
            # Create a new file with the JSON array containing the entry
            with open(json_file, "w", encoding="utf-8") as f:
                f.write("[")
                f.write(json.dumps(entry, cls=CustomJSONEncoder))
                f.write("]")


def setup_logging() -> tuple[logging.Logger, logging.Logger, DataLogger]:
    """Configures the logging system with daily rotation.

    Returns:
        tuple: (logger_generic, logger_errors, data_logger)
    """
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Clean up old logs (> 30 days)
    cleanup_old_logs(logs_dir)

    # Log format
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Generic logger (INFO+)
    generic_logger = logging.getLogger("geocaching.generic")
    generic_logger.setLevel(logging.INFO)

    if not generic_logger.handlers:  # Avoid duplicate handlers
        generic_handler = logging.handlers.TimedRotatingFileHandler(
            filename=logs_dir / "generic.log", when="midnight", interval=1, encoding="utf-8"
        )
        generic_handler.suffix = "%Y-%m-%d"
        generic_handler.setFormatter(formatter)
        generic_logger.addHandler(generic_handler)

    # Error logger (ERROR+)
    error_logger = logging.getLogger("geocaching.errors")
    error_logger.setLevel(logging.ERROR)

    if not error_logger.handlers:  # Avoid duplicate handlers
        error_handler = logging.handlers.TimedRotatingFileHandler(
            filename=logs_dir / "errors.log", when="midnight", interval=1, encoding="utf-8"
        )
        error_handler.suffix = "%Y-%m-%d"
        error_handler.setFormatter(formatter)
        error_logger.addHandler(error_handler)

    # Data logger for JSON
    data_logger = DataLogger(str(logs_dir))

    return generic_logger, error_logger, data_logger


def cleanup_old_logs(logs_dir: Path, retention_days: int = 30) -> None:
    """Deletes log files older than retention_days."""
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d")

    # File patterns to clean up
    patterns = [
        f"{logs_dir}/*-generic.log*",
        f"{logs_dir}/*-errors.log*",
        f"{logs_dir}/*-data.json",
        f"{logs_dir}/generic.log*",
        f"{logs_dir}/errors.log*",
    ]

    for pattern in patterns:
        for file_path in glob.glob(pattern):
            file_name = os.path.basename(file_path)

            # Extract the date from the filename
            for date_part in file_name.split("-"):
                if len(date_part) == 10 and date_part.count("-") == 2:
                    try:
                        if date_part < cutoff_str:
                            os.remove(file_path)
                            print(f"Deleted: {file_path}")
                        break
                    except (ValueError, OSError):
                        continue


# Instance globale (lazy initialization)
_loggers: Optional[tuple[logging.Logger, logging.Logger, DataLogger]] = None


def get_loggers() -> tuple[logging.Logger, logging.Logger, DataLogger]:
    """Returns the configured loggers (singleton)."""
    global _loggers
    if _loggers is None:
        _loggers = setup_logging()
    return _loggers


def extract_user_data(user_id: Optional[ObjectId] = None, request=None) -> dict[str, Any]:
    """Extracts user data for logging."""
    user_data = {}

    if user_id:
        user_data["user_id"] = user_id

    if request:
        # IP from FastAPI request
        if hasattr(request, "client") and request.client:
            user_data["ip"] = request.client.host

        # Optional User-Agent
        if hasattr(request, "headers"):
            user_agent = request.headers.get("user-agent")
            if user_agent:
                user_data["user_agent"] = user_agent

    return user_data
