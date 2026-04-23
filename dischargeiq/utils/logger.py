"""
dischargeiq/utils/logger.py

Configures the project-wide 'dischargeiq' logger with dual output:
console (stdout) and a per-session file at logs/session_YYYYMMDD_HHMMSS.log.
A new log file is created each time configure_logging() is called without
prior handlers — meaning each server startup gets its own log.

Call configure_logging() once at application startup from main.py and
streamlit_app.py. All module-level loggers (logging.getLogger(__name__))
propagate to the 'dischargeiq' root logger automatically.

Depends on: Python standard library only.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# Log format expected by spec: [TIMESTAMP] [LEVEL] [MODULE] message
_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Resolved to DischargeIQ/logs/ regardless of working directory.
_LOGS_DIR = Path(__file__).parent.parent.parent / "logs"


def configure_logging(log_level: int = logging.DEBUG) -> Path:
    """
    Configure the 'dischargeiq' root logger with console and file handlers.

    Idempotent: if handlers are already attached (e.g. on a Streamlit rerender),
    this function returns immediately without duplicating handlers.

    Creates the logs/ directory if it does not exist. The log file name encodes
    the startup timestamp so separate runs do not overwrite each other.

    Args:
        log_level: Minimum level captured by both handlers. Defaults to DEBUG
                   so dev output is verbose. Set to INFO in production.

    Returns:
        Path: Absolute path to the log file created for this session, or the
              existing log file if logging was already configured.
    """
    root_logger = logging.getLogger("dischargeiq")

    # Idempotency guard — Streamlit rerenders call module-level code repeatedly.
    # Checking handlers prevents duplicate log lines per request.
    if root_logger.handlers:
        # Return the path of the existing file handler.
        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                return Path(handler.baseFilename)
        return _LOGS_DIR  # fallback if somehow no file handler found

    root_logger.setLevel(log_level)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

    # ── Console handler (stdout) ──────────────────────────────────────────────
    # Outputs at DEBUG and above so developers see everything in the terminal.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # ── File handler (session log file) ──────────────────────────────────────
    # One file per startup, named by timestamp, in the logs/ directory.
    # Buffered writes (default) are fine — flushes on close/process exit.
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_path = _LOGS_DIR / f"session_{timestamp}.log"

    file_handler = logging.FileHandler(log_file_path, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    root_logger.info(
        "Logging initialised — session log: %s", log_file_path
    )
    return log_file_path
