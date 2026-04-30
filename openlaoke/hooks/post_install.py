"""Post-install hook for OpenLaoKe with detailed error logging."""

from __future__ import annotations

import os
import sys
import traceback


def post_install():
    """Run post-installation setup with detailed logging."""
    try:
        from openlaoke.utils.install_logger import get_install_logger

        logger = get_install_logger()
        logger.log_system_info()
        logger.log_environment()

        logger.info("Starting post-installation setup...")

        _verify_installation(logger)
        _setup_directories(logger)
        _verify_dependencies(logger)
        _check_model_requirements(logger)

        logger.info("Post-installation setup completed successfully!")

    except Exception as e:
        _handle_install_error(e)
        sys.exit(1)


def _verify_installation(logger) -> None:
    """Verify core installation."""
    logger.info("Verifying OpenLaoKe installation...")

    try:
        from openlaoke import __version__

        logger.info(f"OpenLaoKe version: {__version__}")
    except ImportError as e:
        logger.error(f"Failed to import openlaoke: {e}")
        raise

    try:
        import pydantic

        logger.info(f"Pydantic version: {pydantic.__version__}")
    except ImportError as e:
        logger.error(f"Pydantic not installed: {e}")
        raise

    try:
        import rich

        logger.info(f"Rich version: {rich.__version__}")
    except ImportError as e:
        logger.error(f"Rich not installed: {e}")
        raise


def _setup_directories(logger) -> None:
    """Create necessary directories."""
    logger.info("Setting up directories...")

    dirs = [
        "~/.openlaoke",
        "~/.openlaoke/sessions",
        "~/.openlaoke/logs",
        "~/.openlaoke/models",
    ]

    for dir_path in dirs:
        full_path = os.path.expanduser(dir_path)
        try:
            os.makedirs(full_path, exist_ok=True)
            logger.info(f"Created directory: {full_path}")
        except OSError as e:
            logger.error(f"Failed to create directory {full_path}: {e}")
            raise


def _verify_dependencies(logger) -> None:
    """Verify all required dependencies."""
    logger.info("Verifying dependencies...")

    required_packages = [
        "anthropic",
        "pydantic",
        "rich",
        "prompt_toolkit",
        "mcp",
        "aiofiles",
        "httpx",
        "pyyaml",
        "watchfiles",
        "tiktoken",
        "jsonschema",
        "chardet",
        "pathspec",
        "setproctitle",
        "websockets",
        "fastapi",
        "uvicorn",
    ]

    missing = []
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            logger.info(f"  ✓ {package}")
        except ImportError:
            missing.append(package)
            logger.warning(f"  ✗ {package} (missing)")

    if missing:
        logger.warning(f"Missing packages: {', '.join(missing)}")
        logger.warning("Run: pip install -e .[dev]")
    else:
        logger.info("All required dependencies installed!")


def _check_model_requirements(logger) -> None:
    """Check for local model support."""
    logger.info("Checking local model support...")

    try:
        import llama_cpp

        logger.info(f"  ✓ llama-cpp-python available (version: {llama_cpp.__version__})")
    except ImportError:
        logger.info("  ⚪ llama-cpp-python not installed (optional, for local GGUF models)")
        logger.info("    Install with: pip install llama-cpp-python")
        logger.info("    Or: pip install openlaoke[local]")

    try:
        import torch

        logger.info(f"  ✓ PyTorch available (version: {torch.__version__})")
        if torch.cuda.is_available():
            logger.info(f"    CUDA available: {torch.cuda.get_device_name(0)}")
    except ImportError:
        logger.info("  ✗ PyTorch not installed (optional)")


def _handle_install_error(error: Exception) -> None:
    """Handle installation errors with detailed logging."""
    from openlaoke.utils.install_logger import get_install_logger

    logger = get_install_logger()
    logger.critical("=" * 60)
    logger.critical("INSTALLATION FAILED")
    logger.critical("=" * 60)
    logger.critical(f"Error: {error}")
    logger.critical(f"Type: {type(error).__name__}")
    logger.critical("")
    logger.critical("Traceback:")
    logger.critical(traceback.format_exc())
    logger.critical("")
    logger.critical(f"Full log saved to: {logger.get_latest_log()}")
    logger.critical("")
    logger.critical("Troubleshooting:")
    logger.critical("1. Check the log file for detailed error information")
    logger.critical("2. Ensure Python 3.11+ is installed")
    logger.critical("3. Try: pip install -e .[dev]")
    logger.critical("4. Report issues at: https://github.com/OpenLaoKe/OpenLaoKe/issues")
    logger.critical("=" * 60)


if __name__ == "__main__":
    post_install()
