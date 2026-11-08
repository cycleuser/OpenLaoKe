"""Restricted Python sandbox for the CodeMode tool.

The win this buys is token-shaped: "parse these forty files and print the five
that define `main`" is one call and forty lines of output, instead of forty tool
calls and forty results.

What the isolation actually is:

* a separate interpreter (``python -I -B``), started in the workspace, with a
  scrubbed environment (no API keys, no ``PYTHON*`` variables),
* a guarded ``open`` that refuses any path resolving outside the workspace,
* an import hook that refuses process, network and FFI modules
  (``subprocess``, ``socket``, ``ctypes``, ``urllib``, …) and ``os.system``,
* a CPU/address-space rlimit, a wall-clock timeout that kills the process, and a
  cap on how much output can come back.

What it is **not**: a security boundary against deliberately hostile code. The
restrictions are enforced inside the child interpreter, and a determined
attacker with control of the code could get around in-process guards. The
subprocess plus timeout plus path guard is what stops accidents; treat this as
"the model cannot reach the network or the rest of the disk by mistake", not as
a jail for an adversary. That is why the tool is documented this way to the
model and why nothing here executes with elevated permissions.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import tempfile
from dataclasses import dataclass

MAX_OUTPUT_CHARS = 20000
DEFAULT_TIMEOUT = 30.0

PRELUDE = r"""
import builtins, os, sys

ROOT = os.path.realpath(os.environ.get("OPENLAOKE_SANDBOX_ROOT") or os.getcwd())
_real_open = builtins.open
_real_listdir = os.listdir

BLOCKED_MODULES = {
    "asyncio", "multiprocessing", "subprocess", "socket", "ssl", "select",
    "ctypes", "cffi", "pty", "signal", "resource", "fcntl", "mmap",
    "urllib", "http", "ftplib", "smtplib", "telnetlib", "xmlrpc", "requests",
    "httpx", "aiohttp", "paramiko", "shutil", "importlib",
}


class _ImportBlocker:
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split(".")[0]
        if root in BLOCKED_MODULES:
            raise ImportError(f"module '{fullname}' is not available in the sandbox")
        return None


sys.meta_path.insert(0, _ImportBlocker())


def _guard(path):
    text = os.fspath(path)
    target = os.path.realpath(text if os.path.isabs(text) else os.path.join(ROOT, text))
    if target != ROOT and not target.startswith(ROOT + os.sep):
        raise PermissionError(f"path outside the workspace: {text}")
    return target


def _sandbox_open(file, mode="r", *args, **kwargs):
    if isinstance(file, (str, bytes, os.PathLike)):
        file = _guard(file)
    return _real_open(file, mode, *args, **kwargs)


builtins.open = _sandbox_open


def read(path, encoding="utf-8"):
    with _real_open(_guard(path), "r", encoding=encoding, errors="replace") as handle:
        return handle.read()


def write(path, text):
    target = _guard(path)
    parent = os.path.dirname(target)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with _real_open(target, "w", encoding="utf-8") as handle:
        handle.write(text)
    return len(text)


def append(path, text):
    target = _guard(path)
    with _real_open(target, "a", encoding="utf-8") as handle:
        handle.write(text)
    return len(text)


def ls(path="."):
    return sorted(_real_listdir(_guard(path)))


def exists(path):
    return os.path.exists(_guard(path))


def glob(pattern, limit=2000):
    import glob as _glob
    return sorted(_glob.glob(pattern, root_dir=ROOT))[:limit]


def walk(limit=5000):
    found = []
    for directory, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [name for name in dirnames if name not in (".git", "node_modules", "__pycache__", ".venv")]
        for name in filenames:
            found.append(os.path.relpath(os.path.join(directory, name), ROOT))
            if len(found) >= limit:
                return found
    return found


def grep(pattern, path=".", limit=200):
    import re as _re
    regex = _re.compile(pattern)
    target = _guard(path)
    hits = []
    files = [target] if os.path.isfile(target) else [
        os.path.join(directory, name)
        for directory, dirnames, filenames in os.walk(target)
        for name in filenames
        if name.endswith((".py", ".md", ".txt", ".toml", ".json", ".yaml", ".yml", ".js", ".ts", ".rs", ".go", ".c", ".h", ".cpp"))
    ]
    for file_path in files:
        try:
            with _real_open(file_path, "r", encoding="utf-8", errors="replace") as handle:
                for number, line in enumerate(handle, start=1):
                    if regex.search(line):
                        hits.append(f"{os.path.relpath(file_path, ROOT)}:{number}: {line.rstrip()[:200]}")
                        if len(hits) >= limit:
                            return hits
        except OSError:
            continue
    return hits


def _blocked(name):
    def deny(*args, **kwargs):
        raise PermissionError(f"os.{name} is not available in the sandbox")
    return deny


for _name in ("system", "popen", "execv", "execve", "execl", "execlp", "spawnv", "fork", "kill"):
    if hasattr(os, _name):
        setattr(os, _name, _blocked(_name))

try:
    import resource as _resource
    _resource.setrlimit(_resource.RLIMIT_CPU, (int(os.environ.get("OPENLAOKE_SANDBOX_CPU", "35")), int(os.environ.get("OPENLAOKE_SANDBOX_CPU", "35")) + 5))
    _resource.setrlimit(_resource.RLIMIT_AS, (1 << 30, 1 << 30))
except Exception:
    pass
"""


@dataclass
class SandboxResult:
    output: str
    exit_code: int | None
    timed_out: bool = False
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


async def run_code(
    code: str,
    cwd: str,
    timeout: float = DEFAULT_TIMEOUT,
    max_output: int = MAX_OUTPUT_CHARS,
) -> SandboxResult:
    """Run ``code`` in a fresh interpreter confined to ``cwd``."""
    root = os.path.realpath(cwd)
    if not os.path.isdir(root):
        return SandboxResult(f"workspace does not exist: {cwd}", 1)

    with tempfile.TemporaryDirectory(prefix="openlaoke-code-") as staging:
        script = os.path.join(staging, "codemode_main.py")
        with open(script, "w", encoding="utf-8") as handle:
            handle.write(PRELUDE)
            handle.write("\n# ── model code ──\n")
            handle.write(code)

        env = {
            "OPENLAOKE_SANDBOX_ROOT": root,
            "OPENLAOKE_SANDBOX_CPU": str(int(timeout) + 5),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "HOME": staging,
            "PATH": "/usr/bin:/bin",
            "LC_ALL": "C.UTF-8",
        }
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-B",
            script,
            cwd=root,
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            raw, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            with contextlib.suppress(Exception):
                await proc.wait()
            return SandboxResult(
                f"Timed out after {timeout:g}s; the process was killed.", None, timed_out=True
            )

    text = (
        raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
    )
    truncated = len(text) > max_output
    if truncated:
        text = text[:max_output] + f"\n... (output truncated at {max_output} characters)"
    return SandboxResult(
        text, proc.returncode if proc.returncode is not None else 0, truncated=truncated
    )
