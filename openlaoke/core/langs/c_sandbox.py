"""C sandbox with clang compilation, sanitizers, and structured error output."""

from __future__ import annotations

import contextlib
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CompileMessage:
    file_path: str | None = None
    line: int | None = None
    column: int | None = None
    severity: str = "info"
    message: str = ""


@dataclass
class CSandboxResult:
    success: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    exec_ms: float = 0.0
    mem_kb: int | None = None
    compile_ms: float = 0.0
    compile_messages: list[CompileMessage] = field(default_factory=list)
    binary_path: str | None = None


_CC_PRIORITY = ["clang", "gcc", "cc"]


class CSandbox:
    def __init__(self) -> None:
        self._compiler: str | None = None

    @property
    def compiler(self) -> str | None:
        if self._compiler is None:
            for cc in _CC_PRIORITY:
                p = subprocess.run(["which", cc], capture_output=True, text=True, timeout=5)
                if p.returncode == 0:
                    self._compiler = cc
                    return self._compiler
            self._compiler = ""
        return self._compiler if self._compiler else None

    @property
    def available(self) -> bool:
        return self.compiler is not None

    def run(
        self,
        code: str,
        input_data: str | None = None,
        timeout_ms: int = 30000,
        workdir: str | None = None,
    ) -> CSandboxResult:
        if not self.available:
            return CSandboxResult(
                success=False,
                exit_code=-1,
                stderr="No C compiler found (tried: clang, gcc, cc)",
            )

        cwd = workdir or os.getcwd()
        src_path: str | None = None
        bin_path: str | None = None

        try:
            compile_start = time.time()
            fd, src_path = tempfile.mkstemp(suffix=".c", dir=cwd)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(code)

            bin_path = tempfile.mktemp(suffix="", dir=cwd)
            compiler = self.compiler or "gcc"
            compile_result = subprocess.run(
                [compiler, "-Wall", "-Wextra", "-fsanitize=address", "-o", bin_path, src_path],
                capture_output=True,
                text=True,
                timeout=30.0,
                cwd=cwd,
            )
            compile_elapsed = (time.time() - compile_start) * 1000.0
            compile_msgs = self._parse_compile_output(compile_result.stderr, compile_result.stdout)

            if compile_result.returncode != 0:
                return CSandboxResult(
                    success=False,
                    exit_code=compile_result.returncode,
                    stderr=compile_result.stderr,
                    compile_ms=compile_elapsed,
                    compile_messages=compile_msgs,
                )

            run_start = time.time()
            run_kwargs: dict[str, Any] = {
                "capture_output": True,
                "text": True,
                "timeout": timeout_ms / 1000.0,
                "cwd": cwd,
            }
            if input_data:
                run_kwargs["input"] = input_data

            run_result = subprocess.run([bin_path], **run_kwargs)
            run_elapsed = (time.time() - run_start) * 1000.0

            return CSandboxResult(
                success=run_result.returncode == 0,
                exit_code=run_result.returncode,
                stdout=run_result.stdout or "",
                stderr=run_result.stderr or "",
                exec_ms=run_elapsed,
                compile_ms=compile_elapsed,
                compile_messages=compile_msgs,
                binary_path=bin_path,
            )
        except subprocess.TimeoutExpired:
            return CSandboxResult(
                success=False,
                exit_code=-1,
                stderr=f"Timeout after {timeout_ms}ms",
            )
        except Exception as e:
            return CSandboxResult(
                success=False,
                exit_code=-1,
                stderr=str(e),
            )
        finally:
            if src_path and os.path.exists(src_path):
                with contextlib.suppress(OSError):
                    os.unlink(src_path)
            if bin_path and os.path.exists(bin_path):
                with contextlib.suppress(OSError):
                    os.unlink(bin_path)

    def _parse_compile_output(self, stderr: str, stdout: str) -> list[CompileMessage]:
        msgs: list[CompileMessage] = []
        pattern = re.compile(r"^(.*?):(\d+):(\d+):\s*(error|warning|note):\s*(.+)$", re.MULTILINE)
        combined = (stderr or "") + "\n" + (stdout or "")
        for m in pattern.finditer(combined):
            msgs.append(
                CompileMessage(
                    file_path=m.group(1).strip(),
                    line=int(m.group(2)),
                    column=int(m.group(3)),
                    severity=m.group(4),
                    message=m.group(5).strip(),
                )
            )
        if not msgs and (stderr or stdout):
            for line in combined.splitlines():
                line = line.strip()
                if line:
                    msgs.append(CompileMessage(message=line))
        return msgs
