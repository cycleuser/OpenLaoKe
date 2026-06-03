"""World sensor — environment perception injected into system prompt.

Inspired by ModelSensor: senses time, system resources, location, and
environment context so the AI knows where/when it's running.
"""

from __future__ import annotations

import datetime
import json
import os
import platform
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SensorData:
    """Single snapshot of world context."""

    timestamp: str = ""
    date: str = ""
    time_str: str = ""
    weekday: str = ""
    timezone: str = ""
    hostname: str = ""
    user: str = ""
    os_name: str = ""
    os_version: str = ""
    arch: str = ""
    python_version: str = ""
    shell: str = ""
    home_dir: str = ""
    work_dir: str = ""
    cpu_count: int = 0
    memory_total_gb: float = 0.0
    memory_available_gb: float = 0.0
    disk_total_gb: float = 0.0
    disk_free_gb: float = 0.0
    is_virtual_env: bool = False
    is_docker: bool = False
    city: str = ""
    country: str = ""

    def to_summary(self) -> str:
        lines = [
            f"Date: {self.date} {self.time_str} ({self.weekday}, {self.timezone})",
            f"Host: {self.hostname} | User: {self.user}",
            f"OS: {self.os_name} {self.os_version} ({self.arch}) | Python: {self.python_version}",
        ]
        if self.city:
            lines.append(f"Location: {self.city}, {self.country} (approximate)")
        lines.append(
            f"Resources: {self.cpu_count} CPU cores | "
            f"{self.memory_available_gb:.1f}/{self.memory_total_gb:.1f} GB RAM | "
            f"{self.disk_free_gb:.1f}/{self.disk_total_gb:.1f} GB disk"
        )
        lines.append(f"Shell: {self.shell} | CWD: {self.work_dir}")
        if self.is_virtual_env:
            lines.append("Running in virtual environment")
        if self.is_docker:
            lines.append("Running in Docker container")
        return "\n".join(lines)

    def to_context_block(self) -> str:
        return f"<world>\n{self.to_summary()}\n</world>"


def sense_world(include_location: bool = False) -> SensorData:
    """Collect environment perception data. Never raises."""

    sd = SensorData()

    try:
        now = datetime.datetime.now()
        sd.timestamp = now.isoformat()
        sd.date = now.strftime("%Y-%m-%d")
        sd.time_str = now.strftime("%H:%M:%S")
        sd.weekday = now.strftime("%A")
        sd.timezone = str(now.astimezone().tzinfo)
    except Exception:
        sd.date = time.strftime("%Y-%m-%d")
        sd.time_str = time.strftime("%H:%M:%S")

    try:
        sd.hostname = socket.gethostname()
    except Exception:
        sd.hostname = platform.node() or "unknown"

    sd.user = os.environ.get("USER", os.environ.get("USERNAME", "unknown"))

    try:
        uname = platform.uname()
        sd.os_name = uname.system
        sd.os_version = uname.release
        sd.arch = platform.machine()
    except Exception:
        sd.os_name = platform.system()
        sd.arch = "unknown"

    sd.python_version = sys.version.split()[0] if sys.version else "unknown"
    sd.shell = os.environ.get("SHELL", os.environ.get("COMSPEC", "unknown"))
    sd.home_dir = str(Path.home())
    try:
        sd.work_dir = os.getcwd()
    except Exception:
        sd.work_dir = sd.home_dir

    try:
        import psutil

        sd.cpu_count = psutil.cpu_count() or 0
        mem = psutil.virtual_memory()
        sd.memory_total_gb = round(mem.total / (1024**3), 1)
        sd.memory_available_gb = round(mem.available / (1024**3), 1)
        if sys.platform == "win32":
            disk = psutil.disk_usage("C:\\")
        else:
            disk = psutil.disk_usage("/")
        sd.disk_total_gb = round(disk.total / (1024**3), 1)
        sd.disk_free_gb = round(disk.free / (1024**3), 1)
    except ImportError:
        pass
    except Exception:
        pass

    sd.is_virtual_env = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )
    sd.is_docker = os.path.exists("/.dockerenv")

    if include_location:
        try:
            loc = _detect_location()
            sd.city = loc.get("city", "")
            sd.country = loc.get("country", "")
        except Exception:
            pass

    return sd


def _detect_location(timeout: int = 3) -> dict[str, str]:
    """Detect approximate location via IP geolocation."""
    try:
        import urllib.request

        req = urllib.request.Request("http://ip-api.com/json/", headers={"User-Agent": "OpenLaoKe"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == "success":
                return {
                    "city": data.get("city", ""),
                    "country": data.get("country", ""),
                    "region": data.get("regionName", ""),
                    "lat": str(data.get("lat", "")),
                    "lon": str(data.get("lon", "")),
                }
    except Exception:
        pass
    return {}
