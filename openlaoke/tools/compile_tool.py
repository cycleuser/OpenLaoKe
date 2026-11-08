"""Compile tool - run a document compiler locally, with a whitelist.

jcode's compile tool sends a document to a remote build service. There is no
reason to leave the machine for that: `latexmk`, `pandoc`, `typst` and Python's
own compiler either exist locally or do not. This tool runs exactly those, from
a whitelist, in the file's directory, with a timeout, and reports which binary is
missing instead of failing obscurely.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import sys
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock

DEFAULT_TIMEOUT = 180.0
MAX_OUTPUT = 8000

# extension -> (compiler key, command template)
RECIPES: dict[str, str] = {
    ".tex": "latex",
    ".md": "pandoc",
    ".markdown": "pandoc",
    ".typ": "typst",
    ".py": "python",
}


class CompileInput(BaseModel):
    path: str = Field(description="Source file to compile, relative to the workspace")
    compiler: str = Field(
        default="auto",
        description="auto | latex | pandoc | typst | python (whitelisted; auto picks by extension)",
    )
    output: str = Field(
        default="",
        description="Output path, relative to the workspace. Defaults to the source name with a new suffix",
    )
    timeout: float = Field(
        default=DEFAULT_TIMEOUT, description="Seconds before the build is killed"
    )


class CompileTool(Tool):
    """Compile a document with a locally installed compiler."""

    name = "Compile"
    description = (
        "Compile a document locally: LaTeX (.tex) via latexmk/pdflatex, Markdown (.md) via "
        "pandoc, Typst (.typ), or syntax-check Python (.py). Only these compilers are used, "
        "the build runs in the file's directory with a timeout, and a missing binary is "
        "reported by name. Returns the compiler output and the paths it produced."
    )
    input_schema = CompileInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        cwd = ctx.app_state.get_cwd()
        raw_path = str(kwargs.get("path") or "").strip()
        if not raw_path:
            return self._error(ctx, "Error: path is required")

        source = os.path.realpath(os.path.join(cwd, raw_path))
        root = os.path.realpath(cwd)
        if source != root and not source.startswith(root + os.sep):
            return self._error(ctx, f"Error: {raw_path} is outside the workspace")
        if not os.path.isfile(source):
            return self._error(ctx, f"Error: no such file: {raw_path}")

        compiler = str(kwargs.get("compiler") or "auto").strip().lower()
        if compiler == "auto":
            compiler = RECIPES.get(os.path.splitext(source)[1].lower(), "")
        if compiler not in ("latex", "pandoc", "typst", "python"):
            return self._error(
                ctx,
                f"Error: cannot tell how to compile {raw_path}. "
                "Pass compiler=latex|pandoc|typst|python.",
            )

        try:
            timeout = max(5.0, min(900.0, float(kwargs.get("timeout") or DEFAULT_TIMEOUT)))
        except (TypeError, ValueError):
            timeout = DEFAULT_TIMEOUT

        workdir = os.path.dirname(source)
        stem = os.path.splitext(os.path.basename(source))[0]
        output = str(kwargs.get("output") or "").strip()
        output_path = os.path.realpath(os.path.join(cwd, output)) if output else ""

        command, produced_hint = self._plan(compiler, source, workdir, stem, output_path)
        if command is None:
            return self._error(
                ctx,
                f"Error: {compiler} is not installed on this machine "
                f"(looked for {', '.join(self._binaries(compiler))}).",
            )

        before = set(os.listdir(workdir))
        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                cwd=workdir,
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
                return self._error(ctx, f"Error: {compiler} timed out after {timeout:g}s")
        except FileNotFoundError:
            return self._error(ctx, f"Error: {compiler} is not installed on this machine")

        text = (
            raw.decode("utf-8", errors="replace")
            if isinstance(raw, (bytes, bytearray))
            else str(raw)
        )
        text = text.strip()
        if len(text) > MAX_OUTPUT:
            text = text[:MAX_OUTPUT] + "\n... (output truncated)"

        if proc.returncode not in (0, None):
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"{compiler} failed (exit {proc.returncode}):\n{text or '(no output)'}",
                is_error=True,
            )

        after = set(os.listdir(workdir))
        new_files = sorted(
            os.path.join(workdir, name)
            for name in (after - before)
            if os.path.isfile(os.path.join(workdir, name))
        )
        if output_path and os.path.exists(output_path):
            new_files.append(output_path)
        rel_new = [os.path.relpath(path, cwd) for path in dict.fromkeys(new_files)]
        lines = [f"{compiler} succeeded."]
        if rel_new:
            lines.append("produced: " + ", ".join(rel_new))
        elif produced_hint:
            lines.append(f"expected output: {produced_hint}")
        if text:
            lines.append(text)
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content="\n".join(lines))

    @staticmethod
    def _binaries(compiler: str) -> list[str]:
        return {
            "latex": ["latexmk", "pdflatex"],
            "pandoc": ["pandoc"],
            "typst": ["typst"],
            "python": ["python"],
        }[compiler]

    def _plan(
        self, compiler: str, source: str, workdir: str, stem: str, output_path: str
    ) -> tuple[list[str] | None, str]:
        """Return the argv to run, or None when the binary is missing."""
        name = os.path.basename(source)

        if compiler == "latex":
            if shutil.which("latexmk"):
                return (
                    [
                        "latexmk",
                        "-pdf",
                        "-interaction=nonstopmode",
                        "-halt-on-error",
                        name,
                    ],
                    f"{stem}.pdf",
                )
            if shutil.which("pdflatex"):
                return (
                    ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", name],
                    f"{stem}.pdf",
                )
            return None, ""

        if compiler == "pandoc":
            if not shutil.which("pandoc"):
                return None, ""
            target = output_path or os.path.join(workdir, f"{stem}.html")
            return (
                ["pandoc", name, "--standalone", "--output", target],
                os.path.relpath(target, workdir),
            )

        if compiler == "typst":
            if not shutil.which("typst"):
                return None, ""
            target = output_path or os.path.join(workdir, f"{stem}.pdf")
            return (["typst", "compile", name, target], os.path.relpath(target, workdir))

        # python: syntax-check only; py_compile writes into __pycache__
        return (
            [sys.executable, "-I", "-B", "-m", "py_compile", name],
            os.path.join("__pycache__", f"{stem}.pyc"),
        )

    @staticmethod
    def _error(ctx: ToolContext, message: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=message, is_error=True)


def register(registry: ToolRegistry) -> None:
    registry.register(CompileTool())
