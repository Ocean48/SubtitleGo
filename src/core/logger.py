import os
import sys
import time
import logging
import threading
import traceback
import subprocess
from collections import deque
from logging.handlers import RotatingFileHandler
from typing import List, Optional, Callable


_LOG_BUFFER: deque = deque(maxlen=1000)
_LOG_LOCK = threading.Lock()
_LOG_LISTENERS: List[Callable[[str], None]] = []
_ACTIVE_LOG_FILE: Optional[str] = None
_LOGGER_INITIALIZED = False


class LogStreamInterceptor:
    """
    Redirects stdout/stderr writes to logging system, persistent file,
    and memory ring buffer while preserving original stream behavior if present.
    """
    def __init__(self, original_stream, log_level: int, stream_name: str):
        self.original_stream = original_stream
        self.log_level = log_level
        self.stream_name = stream_name
        self.line_buffer = ""
        self._lock = threading.Lock()

    def write(self, message: str):
        if not message:
            return

        if self.original_stream and hasattr(self.original_stream, "write"):
            try:
                self.original_stream.write(message)
                if hasattr(self.original_stream, "flush"):
                    self.original_stream.flush()
            except Exception:
                pass

        with self._lock:
            self.line_buffer += message
            while "\n" in self.line_buffer:
                line, self.line_buffer = self.line_buffer.split("\n", 1)
                line = line.rstrip("\r")
                if line:
                    _append_to_log_buffer(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{self.stream_name.upper()}] {line}")
                    root_logger = logging.getLogger("SubtitleGo")
                    root_logger.log(self.log_level, line)

    def flush(self):
        if self.original_stream and hasattr(self.original_stream, "flush"):
            try:
                self.original_stream.flush()
            except Exception:
                pass
        with self._lock:
            if self.line_buffer.strip():
                line = self.line_buffer.strip()
                self.line_buffer = ""
                _append_to_log_buffer(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{self.stream_name.upper()}] {line}")
                root_logger = logging.getLogger("SubtitleGo")
                root_logger.log(self.log_level, line)


class MemoryBufferLogHandler(logging.Handler):
    """Logging handler that retains the last N formatted logs in memory."""
    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            _append_to_log_buffer(msg)
        except Exception:
            self.handleError(record)


def _append_to_log_buffer(formatted_msg: str):
    with _LOG_LOCK:
        _LOG_BUFFER.append(formatted_msg)
        listeners = list(_LOG_LISTENERS)
    for listener in listeners:
        try:
            listener(formatted_msg)
        except Exception:
            pass


def get_app_root_dir() -> str:
    """Returns application root folder."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def resolve_log_file_path() -> str:
    """
    Resolves the log file path:
    1. `<app_root>/logs/subtitlego.log` (Primary)
    2. Fallback to user local appdata if `<app_root>/logs` is not writable.
    """
    app_root = get_app_root_dir()
    preferred_dir = os.path.join(app_root, "logs")
    preferred_file = os.path.join(preferred_dir, "subtitlego.log")

    try:
        os.makedirs(preferred_dir, exist_ok=True)
        test_file = os.path.join(preferred_dir, ".write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return preferred_file
    except Exception:
        pass

    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        user_log_dir = os.path.join(local_app_data, "SubtitleStudio", "logs")
    elif sys.platform == "darwin":
        user_log_dir = os.path.expanduser("~/Library/Logs/SubtitleStudio")
    else:
        user_log_dir = os.path.expanduser("~/.local/state/subtitlestudio/logs")

    os.makedirs(user_log_dir, exist_ok=True)
    return os.path.join(user_log_dir, "subtitlego.log")


def setup_app_logging() -> str:
    """
    Initializes root logging system, file rotation, and stream redirection.
    Returns the resolved absolute path to logs/subtitlego.log.
    """
    global _ACTIVE_LOG_FILE, _LOGGER_INITIALIZED
    if _LOGGER_INITIALIZED:
        return _ACTIVE_LOG_FILE or resolve_log_file_path()

    log_path = resolve_log_file_path()
    _ACTIVE_LOG_FILE = log_path
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear existing handlers
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Rotating File Handler (5 MB per file, 3 backups)
    try:
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not open log file handler: {e}")

    # 2. In-memory Buffer Handler for UI
    mem_handler = MemoryBufferLogHandler()
    mem_handler.setLevel(logging.INFO)
    mem_handler.setFormatter(formatter)
    root_logger.addHandler(mem_handler)

    # 3. Intercept stdout and stderr
    sys.stdout = LogStreamInterceptor(sys.__stdout__, logging.INFO, "stdout")
    sys.stderr = LogStreamInterceptor(sys.__stderr__, logging.ERROR, "stderr")

    _LOGGER_INITIALIZED = True
    logging.getLogger("SubtitleGo").info(f"Logging initialized. Log file: {log_path}")

    return log_path


def get_log_file_path() -> str:
    global _ACTIVE_LOG_FILE
    if _ACTIVE_LOG_FILE and os.path.exists(_ACTIVE_LOG_FILE):
        return _ACTIVE_LOG_FILE
    return resolve_log_file_path()


def get_recent_logs() -> str:
    with _LOG_LOCK:
        return "\n".join(_LOG_BUFFER)


def clear_recent_logs():
    with _LOG_LOCK:
        _LOG_BUFFER.clear()


def add_log_listener(callback: Callable[[str], None]):
    with _LOG_LOCK:
        if callback not in _LOG_LISTENERS:
            _LOG_LISTENERS.append(callback)


def remove_log_listener(callback: Callable[[str], None]):
    with _LOG_LOCK:
        if callback in _LOG_LISTENERS:
            _LOG_LISTENERS.remove(callback)


def open_log_file():
    """Opens logs/subtitlego.log using the system default text editor."""
    path = get_log_file_path()
    if os.path.isfile(path):
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])


def open_log_directory():
    """Opens the directory containing logs/subtitlego.log in system file explorer."""
    path = get_log_file_path()
    folder = os.path.dirname(path)
    if os.path.isdir(folder):
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.run(["open", folder])
        else:
            subprocess.run(["xdg-open", folder])


def install_global_exception_handler():
    """Captures uncaught exceptions from main thread and logs full tracebacks."""
    def _uncaught_exception_hook(exctype, value, tb):
        err_msg = "".join(traceback.format_exception(exctype, value, tb))
        logging.getLogger("SubtitleGo").critical(f"Uncaught exception:\n{err_msg}")
        # Print to stderr to ensure interceptor and console also receive it
        if sys.__stderr__:
            sys.__stderr__.write(err_msg)

    sys.excepthook = _uncaught_exception_hook
