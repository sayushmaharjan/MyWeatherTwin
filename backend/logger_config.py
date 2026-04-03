"""
WeatherTwin — Centralized Logging Configuration
Provides structured logging with file rotation, console output,
and integration with the monitoring system.
"""

import os
import sys
import logging
import logging.handlers
import json
from datetime import datetime
from pathlib import Path


# ──────────────────────────────────────────────
# Log Directory Setup
# ──────────────────────────────────────────────

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────
# Custom JSON Formatter
# ──────────────────────────────────────────────

class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for machine-readable logs."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields
        for key in ["service", "city", "user_id", "latency_ms",
                     "api_endpoint", "status_code", "tokens"]:
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        return json.dumps(log_entry)


class ColoredConsoleFormatter(logging.Formatter):
    """Colored console formatter for human-readable output."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[41m",  # Red background
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.utcnow().strftime("%H:%M:%S")
        prefix = f"{color}[{timestamp}] [{record.levelname:8s}]{self.RESET}"
        msg = f"{prefix} {record.name}: {record.getMessage()}"

        # Add extra context if available
        extras = []
        for key in ["service", "city", "latency_ms", "status_code"]:
            if hasattr(record, key):
                extras.append(f"{key}={getattr(record, key)}")
        if extras:
            msg += f" ({', '.join(extras)})"

        if record.exc_info and record.exc_info[0]:
            msg += f"\n{self.formatException(record.exc_info)}"

        return msg


# ──────────────────────────────────────────────
# Logger Factory
# ──────────────────────────────────────────────

def get_logger(name: str, level: str = None) -> logging.Logger:
    """
    Get a configured logger with console + file handlers.
    
    Usage:
        from logger_config import get_logger
        logger = get_logger("weather_service")
        logger.info("Fetching weather", extra={"city": "NYC", "service": "OpenMeteo"})
    """
    logger = logging.getLogger(f"weathertwin.{name}")

    # Don't add handlers if they already exist
    if logger.handlers:
        return logger

    log_level = getattr(logging, (level or os.getenv("LOG_LEVEL", "INFO")).upper(), logging.INFO)
    logger.setLevel(log_level)
    logger.propagate = False

    # Console handler (colored, human-readable)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(ColoredConsoleFormatter())
    logger.addHandler(console_handler)

    # JSON file handler (structured, machine-readable, rotating)
    json_file = os.path.join(LOG_DIR, f"{name}.jsonl")
    file_handler = logging.handlers.RotatingFileHandler(
        json_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)  # Capture everything to file
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)

    # Error-only file handler (for quick error review)
    error_file = os.path.join(LOG_DIR, "errors.jsonl")
    error_handler = logging.handlers.RotatingFileHandler(
        error_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    logger.addHandler(error_handler)

    return logger


# ──────────────────────────────────────────────
# Pre-configured Loggers
# ──────────────────────────────────────────────

# These can be imported directly
weather_logger = get_logger("weather_service")
llm_logger = get_logger("llm_service")
db_logger = get_logger("db_service")
api_logger = get_logger("api")
app_logger = get_logger("app")
auth_logger = get_logger("auth")


# ──────────────────────────────────────────────
# Log File Reader (for in-app log viewer)
# ──────────────────────────────────────────────

def read_log_file(name: str, lines: int = 100, level_filter: str = None) -> list:
    """
    Read the last N lines from a structured JSON log file.
    Returns list of parsed log entries.
    """
    log_file = os.path.join(LOG_DIR, f"{name}.jsonl")
    if not os.path.exists(log_file):
        return []

    entries = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()

        # Read from the end
        for line in reversed(all_lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if level_filter and entry.get("level") != level_filter.upper():
                    continue
                entries.append(entry)
                if len(entries) >= lines:
                    break
            except json.JSONDecodeError:
                continue

    except Exception as e:
        entries.append({
            "timestamp": datetime.utcnow().isoformat(),
            "level": "ERROR",
            "message": f"Failed to read log file: {e}",
        })

    return entries


def get_log_file_names() -> list:
    """Get list of available log files."""
    if not os.path.exists(LOG_DIR):
        return []
    return [
        f.replace(".jsonl", "")
        for f in os.listdir(LOG_DIR)
        if f.endswith(".jsonl")
    ]


def get_log_stats() -> dict:
    """Get statistics about log files."""
    stats = {}
    if not os.path.exists(LOG_DIR):
        return stats

    for f in os.listdir(LOG_DIR):
        if f.endswith(".jsonl"):
            path = os.path.join(LOG_DIR, f)
            size = os.path.getsize(path)
            line_count = 0
            try:
                with open(path, "r") as fh:
                    line_count = sum(1 for _ in fh)
            except Exception:
                pass

            stats[f.replace(".jsonl", "")] = {
                "file": f,
                "size_kb": round(size / 1024, 1),
                "entries": line_count,
            }

    return stats