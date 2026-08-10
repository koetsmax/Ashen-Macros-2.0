import atexit
import faulthandler
import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler

from core.settings import DATA_DIR

LOG_FILE_NAME = "ashen-macros.log"
FAULT_FILE_NAME = "ashen-macros.fault.log"
MAX_BYTES = 1 * 1024 * 1024
BACKUP_COUNT = 5

_CONFIGURED = False
_FAULT_FILE = None


def log_file_path() -> str:
    """Absolute path to the rotating macros log file."""
    return os.path.join(DATA_DIR, LOG_FILE_NAME)


def fault_log_path() -> str:
    """Absolute path to the native crash / faulthandler dump file."""
    return os.path.join(DATA_DIR, FAULT_FILE_NAME)


def setup_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED, _FAULT_FILE
    if _CONFIGURED:
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    log_path = log_file_path()
    fault_path = fault_log_path()

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
    threading.excepthook = _log_unhandled_thread_exception
    atexit.register(_log_atexit)

    # Native access violations / fatal signals never reach Python hooks.
    # Dump all thread stacks into a sibling file when the interpreter can.
    try:
        _FAULT_FILE = open(fault_path, "a", encoding="utf-8")
        faulthandler.enable(file=_FAULT_FILE, all_threads=True)
    except Exception:
        logging.getLogger(__name__).warning(
            "Could not enable faulthandler at %s", fault_path, exc_info=True
        )

    logging.getLogger(__name__).info("Logging initialized at %s", log_path)
    logging.getLogger(__name__).info("Fault dumps (if any) at %s", fault_path)
    _CONFIGURED = True


def _log_unhandled_exception(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logging.getLogger("ashen_macros").critical(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_tb),
    )


def _log_unhandled_thread_exception(args):
    if args.exc_type is SystemExit:
        return
    name = getattr(args.thread, "name", None) or repr(args.thread)
    logging.getLogger("ashen_macros").critical(
        "Uncaught thread exception in %s",
        name,
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


def _log_atexit():
    logging.getLogger("ashen_macros").info("atexit: process shutting down")
