"""Rust sandbox with cargo check/test and clippy integration."""

from __future__ import annotations

import contextlib
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RustDiagnostic:
    severity: str
    message: str
    line: int | None = None
    column: int | None = None
    code: str | None = None


@dataclass
class RustSandboxResult:
    success: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    check_ms: float = 0.0
    build_ms: float = 0.0
    test_ms: float = 0.0
    diagnostics: list[RustDiagnostic] = field(default_factory=list)


class RustSandbox:
    def __init__(self) -> None:
        self._cargo: str | None = None
        self._rustc: str | None = None

    @property
    def cargo(self) -> str | None:
        if self._cargo is None:
            found = self._find_bin("cargo")
            if found:
                self._cargo = found
        return self._cargo

    @property
    def rustc(self) -> str | None:
        if self._rustc is None:
            found = self._find_bin("rustc")
            if found:
                self._rustc = found
        return self._rustc

    @property
    def available(self) -> bool:
        return self.cargo is not None

    def _find_bin(self, name: str) -> str | None:
        p = subprocess.run(
            ["which", name], capture_output=True, text=True, timeout=5
        )
        if p.returncode == 0:
            return p.stdout.strip()
        return None

    def run(
        self,
        code: str,
        timeout_ms: int = 60000,
        workdir: str | None = None,
    ) -> RustSandboxResult:
        if not self.available:
            return RustSandboxResult(
                success=False,
                exit_code=-1,
                stderr="Rust toolchain not found (cargo not in PATH)",
            )

        cwd = workdir or os.getcwd()
        project_dir: str | None = None

        try:
            project_dir = tempfile.mkdtemp(prefix="rust_", dir=cwd)
            src_dir = os.path.join(project_dir, "src")
            os.makedirs(src_dir, exist_ok=True)

            cargo_toml = (
                '[package]\n'
                'name = "sandbox"\n'
                'version = "0.1.0"\n'
                'edition = "2024"\n'
            )
            with open(os.path.join(project_dir, "Cargo.toml"), "w", encoding="utf-8") as f:
                f.write(cargo_toml)

            with open(os.path.join(src_dir, "main.rs"), "w", encoding="utf-8") as f:
                f.write(code)

            check_start = time.time()
            check_result = subprocess.run(
                [self.cargo, "check", "--message-format=json"],
                capture_output=True,
                text=True,
                timeout=min(timeout_ms / 1000.0, 60.0),
                cwd=project_dir,
            )
            check_elapsed = (time.time() - check_start) * 1000.0
            diagnostics = self._parse_cargo_json(check_result.stdout)

            if check_result.returncode != 0:
                return RustSandboxResult(
                    success=False,
                    exit_code=check_result.returncode,
                    stderr=check_result.stderr or "",
                    check_ms=check_elapsed,
                    diagnostics=diagnostics,
                )

            build_start = time.time()
            build_result = subprocess.run(
                [self.cargo, "build"],
                capture_output=True,
                text=True,
                timeout=min(timeout_ms / 1000.0, 60.0),
                cwd=project_dir,
            )
            build_elapsed = (time.time() - build_start) * 1000.0

            if build_result.returncode != 0:
                return RustSandboxResult(
                    success=False,
                    exit_code=build_result.returncode,
                    stderr=build_result.stderr or "",
                    check_ms=check_elapsed,
                    build_ms=build_elapsed,
                    diagnostics=diagnostics,
                )

            test_start = time.time()
            test_result = subprocess.run(
                [self.cargo, "test"],
                capture_output=True,
                text=True,
                timeout=min(timeout_ms / 1000.0, 60.0),
                cwd=project_dir,
            )
            test_elapsed = (time.time() - test_start) * 1000.0

            return RustSandboxResult(
                success=test_result.returncode == 0,
                exit_code=test_result.returncode,
                stdout=test_result.stdout or "",
                stderr=test_result.stderr or "",
                check_ms=check_elapsed,
                build_ms=build_elapsed,
                test_ms=test_elapsed,
                diagnostics=diagnostics,
            )
        except subprocess.TimeoutExpired:
            return RustSandboxResult(
                success=False,
                exit_code=-1,
                stderr=f"Timeout after {timeout_ms}ms",
            )
        except Exception as e:
            return RustSandboxResult(
                success=False,
                exit_code=-1,
                stderr=str(e),
            )
        finally:
            if project_dir and os.path.exists(project_dir):
                with contextlib.suppress(OSError):
                    import shutil

                    shutil.rmtree(project_dir)

    def _parse_cargo_json(self, stdout: str) -> list[RustDiagnostic]:
        results: list[RustDiagnostic] = []
        try:
            import json

            for line in stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                diagnostic: RustDiagnostic | None = self._convert_msg(msg)
                if diagnostic:
                    results.append(diagnostic)
        except Exception:
            pass
        return results

    def _convert_msg(self, msg: dict[str, Any]) -> RustDiagnostic | None:
        reason = msg.get("reason", "")
        if reason != "compiler-message" and reason != "compiler-artifact":
            return None
        inner = msg.get("message", {})
        spans = inner.get("spans", [])
        line = None
        column = None
        if spans:
            line = spans[0].get("line_start")
            column = spans[0].get("column_start")
        code_info = inner.get("code")
        code_str = None
        if isinstance(code_info, dict):
            code_str = code_info.get("code")
        return RustDiagnostic(
            severity=inner.get("level", "warning"),
            message=inner.get("message", ""),
            line=line,
            column=column,
            code=code_str,
        )
