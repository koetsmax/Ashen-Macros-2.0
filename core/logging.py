import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from core.settings import DATA_DIR

LOG_FILE_NAME = "ashen-macros.log"
MAX_BYTES = 1 * 1024 * 1024
BACKUP_COUNT = 5

_CONFIGURED = False


def log_file_path() -> str:
    """Absolute path to the rotating macros log file."""
    return os.path.join(DATA_DIR, LOG_FILE_NAME)


def setup_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    log_path = log_file_path()

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    sys.excepthook = _log_unhandled_exception

    logging.getLogger(__name__).info("Logging initialized at %s", log_path)
    _CONFIGURED = True


def _log_unhandled_exception(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logging.getLogger("ashen_macros").critical(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_tb),
    )
