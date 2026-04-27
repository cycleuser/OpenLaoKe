"""Detailed installation logger with file and console output."""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path


class InstallLogger:
    """Logger for installation and setup processes with detailed file logging."""

    _instance: InstallLogger | None = None

    def __init__(self, log_dir: str | None = None) -> None:
        self.log_dir = log_dir or os.path.expanduser("~/.openlaoke/logs")
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(
            self.log_dir, f"install_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        self.logger = logging.getLogger("openlaoke.install")
        self.logger.setLevel(logging.DEBUG)
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("%(levelname)s: %(message)s")
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

    @classmethod
    def get_instance(cls, log_dir: str | None = None) -> InstallLogger:
        if cls._instance is None:
            cls._instance = cls(log_dir)
        return cls._instance

    def info(self, message: str) -> None:
        self.logger.info(message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)

    def error(self, message: str) -> None:
        self.logger.error(message)

    def debug(self, message: str) -> None:
        self.logger.debug(message)

    def critical(self, message: str) -> None:
        self.logger.critical(message)

    def log_exception(self, exception: Exception, context: str = "") -> None:
        self.logger.exception(f"{context}: {exception}")

    def log_system_info(self) -> None:
        import platform
        import sys

        self.info("=" * 60)
        self.info("OpenLaoKe Installation Log")
        self.info("=" * 60)
        self.info(f"Timestamp: {datetime.now().isoformat()}")
        self.info(f"Python: {sys.version}")
        self.info(f"Platform: {platform.platform()}")
        self.info(f"Machine: {platform.machine()}")
        self.info(f"Processor: {platform.processor()}")
        self.info(f"Working Dir: {os.getcwd()}")
        self.info(f"User Home: {os.path.expanduser('~')}")
        self.info("=" * 60)

    def log_environment(self) -> None:
        self.info("Environment Variables:")
        relevant_vars = [
            "PATH",
            "PYTHONPATH",
            "VIRTUAL_ENV",
            "CONDA_PREFIX",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "NO_PROXY",
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
        ]
        for var in relevant_vars:
            value = os.environ.get(var, "NOT SET")
            if var.endswith("API_KEY") and value != "NOT SET":
                value = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "***"
            self.info(f"  {var}={value}")

    def get_latest_log(self) -> str:
        logs_dir = Path(self.log_dir)
        log_files = sorted(logs_dir.glob("install_*.log"), key=os.path.getmtime)
        if log_files:
            return str(log_files[-1])
        return ""


def get_install_logger() -> InstallLogger:
    return InstallLogger.get_instance()
