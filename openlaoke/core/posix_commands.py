"""POSIX-compatible command layer for cross-platform support.

Provides unified interface for common operations across different OS:
- Linux/Unix (POSIX-compliant)
- macOS (Darwin, mostly POSIX)
- Windows (different commands)

This allows small models to use unified commands without worrying about OS differences.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class OS(StrEnum):
    LINUX = "linux"
    MACOS = "darwin"
    WINDOWS = "windows"
    FREEBSD = "freebsd"
    UNKNOWN = "unknown"


@dataclass
class CommandMapping:
    """Mapping between unified command and OS-specific commands."""

    unified: str
    linux: str
    macos: str
    windows: str
    description: str


class POSIXCommands:
    """POSIX-compatible command mappings."""

    COMMANDS = {
        "list_files": CommandMapping(
            unified="list_files",
            linux="ls -la",
            macos="ls -la",
            windows="dir",
            description="List all files in directory",
        ),
        "list_files_simple": CommandMapping(
            unified="list_files_simple",
            linux="ls",
            macos="ls",
            windows="dir",
            description="List files (simple)",
        ),
        "change_directory": CommandMapping(
            unified="change_directory",
            linux="cd",
            macos="cd",
            windows="cd",
            description="Change current directory",
        ),
        "print_working_directory": CommandMapping(
            unified="print_working_directory",
            linux="pwd",
            macos="pwd",
            windows="cd",
            description="Print working directory",
        ),
        "create_directory": CommandMapping(
            unified="create_directory",
            linux="mkdir -p",
            macos="mkdir -p",
            windows="mkdir",
            description="Create directory (with parents)",
        ),
        "remove_file": CommandMapping(
            unified="remove_file",
            linux="rm",
            macos="rm",
            windows="del",
            description="Remove a file",
        ),
        "remove_directory": CommandMapping(
            unified="remove_directory",
            linux="rm -rf",
            macos="rm -rf",
            windows="rmdir /s /q",
            description="Remove directory recursively",
        ),
        "copy_file": CommandMapping(
            unified="copy_file",
            linux="cp",
            macos="cp",
            windows="copy",
            description="Copy file",
        ),
        "move_file": CommandMapping(
            unified="move_file",
            linux="mv",
            macos="mv",
            windows="move",
            description="Move/rename file",
        ),
        "find_file": CommandMapping(
            unified="find_file",
            linux="find . -name",
            macos="find . -name",
            windows="dir /s /b",
            description="Find files by name",
        ),
        "search_in_files": CommandMapping(
            unified="search_in_files",
            linux="grep -r",
            macos="grep -r",
            windows="findstr /s",
            description="Search text in files",
        ),
        "view_file": CommandMapping(
            unified="view_file",
            linux="cat",
            macos="cat",
            windows="type",
            description="View file content",
        ),
        "view_file_head": CommandMapping(
            unified="view_file_head",
            linux="head -n 20",
            macos="head -n 20",
            windows="more",
            description="View first lines of file",
        ),
        "view_file_tail": CommandMapping(
            unified="view_file_tail",
            linux="tail -n 20",
            macos="tail -n 20",
            windows="more",
            description="View last lines of file",
        ),
        "change_permissions": CommandMapping(
            unified="change_permissions",
            linux="chmod",
            macos="chmod",
            windows="icacls",
            description="Change file permissions",
        ),
        "check_process": CommandMapping(
            unified="check_process",
            linux="ps aux | grep",
            macos="ps aux | grep",
            windows="tasklist | findstr",
            description="Check running processes",
        ),
        "kill_process": CommandMapping(
            unified="kill_process",
            linux="kill",
            macos="kill",
            windows="taskkill /F /PID",
            description="Kill a process",
        ),
        "environment_variables": CommandMapping(
            unified="environment_variables",
            linux="env",
            macos="env",
            windows="set",
            description="Show environment variables",
        ),
        "set_env_variable": CommandMapping(
            unified="set_env_variable",
            linux="export",
            macos="export",
            windows="set",
            description="Set environment variable",
        ),
        "check_network": CommandMapping(
            unified="check_network",
            linux="ping -c 4",
            macos="ping -c 4",
            windows="ping -n 4",
            description="Check network connectivity",
        ),
        "download_file": CommandMapping(
            unified="download_file",
            linux="wget",
            macos="curl -O",
            windows="curl -O",
            description="Download file from URL",
        ),
        "compress_file": CommandMapping(
            unified="compress_file",
            linux="tar -czf",
            macos="tar -czf",
            windows="tar -a -c -f",
            description="Compress files/directories",
        ),
        "extract_file": CommandMapping(
            unified="extract_file",
            linux="tar -xzf",
            macos="tar -xzf",
            windows="tar -xzf",
            description="Extract compressed file",
        ),
    }

    PYTHON_EQUIVALENTS = {
        "list_files": "import os; print('\\n'.join(os.listdir('.')))",
        "list_files_simple": "import os; print('\\n'.join(os.listdir('.')))",
        "print_working_directory": "import os; print(os.getcwd())",
        "create_directory": "import os; os.makedirs({path}, exist_ok=True)",
        "remove_file": "import os; os.remove({path})",
        "remove_directory": "import shutil; shutil.rmtree({path})",
        "copy_file": "import shutil; shutil.copy({src}, {dst})",
        "move_file": "import shutil; shutil.move({src}, {dst})",
        "view_file": "with open({path}) as f: print(f.read())",
        "environment_variables": "import os; print(os.environ)",
    }

    @classmethod
    def get_command(cls, unified_name: str, target_os: OS | None = None) -> str:
        """Get OS-specific command for a unified command name.

        Args:
            unified_name: Unified command name
            target_os: Target OS (auto-detect if None)

        Returns:
            OS-specific command string
        """
        if target_os is None:
            target_os = cls.detect_os()

        if unified_name not in cls.COMMANDS:
            return unified_name

        mapping = cls.COMMANDS[unified_name]

        if target_os == OS.LINUX:
            return mapping.linux
        elif target_os == OS.MACOS:
            return mapping.macos
        elif target_os == OS.WINDOWS:
            return mapping.windows
        else:
            return mapping.linux

    @classmethod
    def get_python_equivalent(cls, unified_name: str) -> str | None:
        """Get Python code equivalent for a unified command.

        Args:
            unified_name: Unified command name

        Returns:
            Python code string or None if not available
        """
        return cls.PYTHON_EQUIVALENTS.get(unified_name)

    @classmethod
    def detect_os(cls) -> OS:
        """Detect current operating system."""
        system = platform.system().lower()

        if system == "linux":
            return OS.LINUX
        elif system == "darwin":
            return OS.MACOS
        elif system == "windows":
            return OS.WINDOWS
        elif system == "freebsd":
            return OS.FREEBSD
        else:
            return OS.UNKNOWN

    @classmethod
    def list_available_commands(cls) -> list[str]:
        """List all available unified commands."""
        return list(cls.COMMANDS.keys())

    @classmethod
    def get_command_info(cls, unified_name: str) -> dict[str, str] | None:
        """Get detailed information about a command."""
        if unified_name not in cls.COMMANDS:
            return None

        mapping = cls.COMMANDS[unified_name]

        return {
            "unified": mapping.unified,
            "linux": mapping.linux,
            "macos": mapping.macos,
            "windows": mapping.windows,
            "description": mapping.description,
            "python": cls.PYTHON_EQUIVALENTS.get(unified_name, "N/A"),
        }


class CommandBuilder:
    """Build commands with arguments in a cross-platform way."""

    def __init__(self, target_os: OS | None = None):
        self.os = target_os or POSIXCommands.detect_os()

    def list_files(self, directory: str = ".", show_all: bool = True) -> str:
        """Build command to list files."""
        if show_all:
            cmd = POSIXCommands.get_command("list_files", self.os)
        else:
            cmd = POSIXCommands.get_command("list_files_simple", self.os)

        if self.os == OS.WINDOWS:
            return f"{cmd} {directory}"
        else:
            return f"{cmd} {directory}"

    def find_files(self, pattern: str, directory: str = ".") -> str:
        """Build command to find files by pattern."""
        cmd = POSIXCommands.get_command("find_file", self.os)

        if self.os == OS.WINDOWS:
            return f"{cmd} {directory}\\{pattern}"
        else:
            return f"{cmd} {directory} {pattern}"

    def search_in_files(self, pattern: str, directory: str = ".") -> str:
        """Build command to search text in files."""
        cmd = POSIXCommands.get_command("search_in_files", self.os)
        return f"{cmd} {pattern} {directory}"

    def create_directory(self, path: str) -> str:
        """Build command to create directory."""
        cmd = POSIXCommands.get_command("create_directory", self.os)
        return f"{cmd} {path}"

    def remove_file(self, path: str) -> str:
        """Build command to remove file."""
        cmd = POSIXCommands.get_command("remove_file", self.os)
        return f"{cmd} {path}"

    def remove_directory(self, path: str) -> str:
        """Build command to remove directory."""
        cmd = POSIXCommands.get_command("remove_directory", self.os)
        return f"{cmd} {path}"

    def copy_file(self, source: str, destination: str) -> str:
        """Build command to copy file."""
        cmd = POSIXCommands.get_command("copy_file", self.os)
        return f"{cmd} {source} {destination}"

    def move_file(self, source: str, destination: str) -> str:
        """Build command to move file."""
        cmd = POSIXCommands.get_command("move_file", self.os)
        return f"{cmd} {source} {destination}"

    def view_file(self, path: str) -> str:
        """Build command to view file."""
        cmd = POSIXCommands.get_command("view_file", self.os)
        return f"{cmd} {path}"

    def download_file(self, url: str, output_file: str | None = None) -> str:
        """Build command to download file."""
        cmd = POSIXCommands.get_command("download_file", self.os)

        if self.os == OS.WINDOWS or self.os == OS.MACOS:
            if output_file:
                return f"curl -o {output_file} {url}"
            return f"{cmd} {url}"
        else:
            if output_file:
                return f"{cmd} -O {url}"
            return f"{cmd} {url}"


def create_command_builder(target_os: OS | None = None) -> CommandBuilder:
    """Create a command builder for specific OS."""
    return CommandBuilder(target_os)


def get_command(unified_name: str, target_os: OS | None = None) -> str:
    """Convenience function to get OS-specific command."""
    return POSIXCommands.get_command(unified_name, target_os)


def get_python_command(unified_name: str) -> str | None:
    """Convenience function to get Python equivalent."""
    return POSIXCommands.get_python_equivalent(unified_name)
