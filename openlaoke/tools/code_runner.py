"""CodeRunner tool - execute code in sandboxed environment with iterative refinement."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.langs.python_sandbox import (
    PythonSandbox,
    StructuredResult,
)
from openlaoke.core.tool import Tool, ToolContext
from openlaoke.types.core_types import ToolResultBlock

MAX_REFINEMENT_ROUNDS = 3


class CodeRunnerInput(BaseModel):
    language: str = Field(description="Language: python, c, rust")
    code: str = Field(description="Code to execute")
    test_code: str | None = Field(default=None, description="Optional test code")
    timeout_ms: int | None = Field(default=None, description="Timeout in ms")
    mem_mb: int | None = Field(default=None, description="Memory limit in MB")


class CodeRunnerTool(Tool):
    name = "code_runner"
    description = (
        "Run code in a sandboxed environment with optional tests. "
        "Supports Python (with static analysis + pytest), C (planned), Rust (planned). "
        "Automatically refines code on failures."
    )
    input_schema = CodeRunnerInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = True
    requires_approval = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        inp = CodeRunnerInput(**kwargs)
        lang = inp.language.lower()

        if lang == "python":
            return await self._run_python(ctx, inp)
        if lang == "c":
            return await self._run_c(ctx, inp)
        if lang == "rust":
            return await self._run_rust(ctx, inp)

        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=f"Unsupported language: {inp.language}",
            is_error=True,
        )

    async def _run_python(
        self,
        ctx: ToolContext,
        inp: CodeRunnerInput,
    ) -> ToolResultBlock:
        sandbox = PythonSandbox()
        timeout = inp.timeout_ms or 30000
        mem = inp.mem_mb or 256

        result: StructuredResult | None = None
        last_code = inp.code
        history: list[str] = []

        for round_num in range(MAX_REFINEMENT_ROUNDS):
            if round_num > 0:
                history.append(f"\n--- Round {round_num} ---")
                history.append(f"Previous code:\n{last_code}")
                history.append(
                    f"Feedback:\n{self._format_result(result) if result else 'No result'}"
                )

            result = sandbox.run(
                code=inp.code,
                timeout_ms=timeout,
                mem_mb=mem,
                run_static_analysis=(round_num == 0),
                run_tests=(inp.test_code is not None),
                test_code=inp.test_code,
            )

            lines = history + [
                f"[Sandbox] exit_code={result.exit_code}",
                f"[Sandbox] exec={result.exec_ms:.0f}ms",
            ]
            if result.mem_kb:
                lines.append(f"[Sandbox] mem={result.mem_kb}KB")
            if result.stdout:
                lines.append("--- stdout ---")
                lines.append(result.stdout[:3000])
            if result.stderr:
                lines.append("--- stderr ---")
                lines.append(result.stderr[:3000])
            if result.analysis:
                lines.append("--- static analysis ---")
                for a in result.analysis:
                    loc = f":{a.line}" if a.line else ""
                    lines.append(f"[{a.tool}/{a.severity}{loc}] {a.message}")
            if result.test_result:
                lines.append("--- test ---")
                lines.append(json.dumps(result.test_result, indent=2))

            if result.success and not result.retry_suggested:
                break

            if round_num < MAX_REFINEMENT_ROUNDS - 1:
                feedback = "\n".join(lines)
                last_code = inp.code
                inp.code = await self._suggest_fix(ctx, inp.code, feedback, inp.language)
                if inp.code == last_code:
                    break

        content = "\n".join(lines)
        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=content,
            is_error=not result.success if result else True,
        )

    def _format_result(self, result: StructuredResult) -> str:
        parts: list[str] = []
        if result.analysis:
            for a in result.analysis:
                loc = f":{a.line}" if a.line else ""
                parts.append(f"[{a.tool}/{a.severity}{loc}] {a.message}")
        return "\n".join(parts)

    async def _suggest_fix(
        self,
        ctx: ToolContext,
        code: str,
        feedback: str,
        language: str,
    ) -> str:
        try:
            from openlaoke.core.multi_provider_api import MultiProviderClient
            from openlaoke.core.state import AppState

            app_state: AppState = ctx.app_state
            if not app_state or not app_state.multi_provider_config:
                return code

            config = app_state.multi_provider_config
            model = config.get_active_model()
            if not model:
                return code

            api = MultiProviderClient(config)
            try:
                system = (
                    f"You are a {language} expert. Fix the code based on the feedback. "
                    "Return ONLY the fixed code, no explanation."
                )
                messages = [
                    {
                        "role": "user",
                        "content": f"Code:\n```\n{code}\n```\n\nFeedback:\n{feedback}",
                    },
                ]
                response, _, _ = await api.send_message(
                    system_prompt=system,
                    messages=messages,
                    model=model,
                )
                if response and response.content:
                    cleaned = self._extract_code(response.content)
                    if cleaned and cleaned != code:
                        return cleaned
            finally:
                import asyncio

                asyncio.create_task(api.close())
        except Exception:
            pass
        return code

    def _extract_code(self, text: str) -> str:
        import re

        m = re.search(r"```(?:\w*\n)?(.*?)```", text, re.DOTALL)
        if m:
            return m.group(1).strip()
        return text.strip()

    async def _run_c(
        self,
        ctx: ToolContext,
        inp: CodeRunnerInput,
    ) -> ToolResultBlock:
        from openlaoke.core.langs.c_sandbox import CSandbox

        sandbox = CSandbox()
        if not sandbox.available:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="No C compiler found. Install clang or gcc to use C support.",
                is_error=True,
            )

        timeout = inp.timeout_ms or 30000
        result = sandbox.run(
            code=inp.code,
            timeout_ms=timeout,
            workdir=None,
        )

        lines: list[str] = []
        lines.append(f"[C] compile={result.compile_ms:.0f}ms exec={result.exec_ms:.0f}ms")
        lines.append(f"[C] exit_code={result.exit_code}")

        if result.stderr:
            lines.append("--- stderr ---")
            lines.append(result.stderr[:3000])
        if result.compile_messages:
            lines.append("--- compiler ---")
            for cm in result.compile_messages:
                loc = f"{cm.file_path}:{cm.line}:{cm.column}" if cm.file_path else ""
                lines.append(f"[{cm.severity} {loc}] {cm.message}")
        if result.stdout:
            lines.append("--- stdout ---")
            lines.append(result.stdout[:3000])

        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content="\n".join(lines),
            is_error=not result.success,
        )

    async def _run_rust(
        self,
        ctx: ToolContext,
        inp: CodeRunnerInput,
    ) -> ToolResultBlock:
        from openlaoke.core.langs.rust_sandbox import RustSandbox

        sandbox = RustSandbox()
        if not sandbox.available:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Rust toolchain not found. Install rustup to use Rust support.",
                is_error=True,
            )

        timeout = inp.timeout_ms or 60000
        result = sandbox.run(
            code=inp.code,
            timeout_ms=timeout,
            workdir=None,
        )

        lines: list[str] = []
        lines.append(
            f"[Rust] check={result.check_ms:.0f}ms build={result.build_ms:.0f}ms"
            f" test={result.test_ms:.0f}ms"
        )
        lines.append(f"[Rust] exit_code={result.exit_code}")

        if result.diagnostics:
            lines.append("--- diagnostics ---")
            for d in result.diagnostics:
                loc = f":{d.line}" if d.line else ""
                code_tag = f" [{d.code}]" if d.code else ""
                lines.append(f"[{d.severity}{loc}]{code_tag} {d.message}")
        if result.stdout:
            lines.append("--- stdout ---")
            lines.append(result.stdout[:3000])
        if result.stderr:
            lines.append("--- stderr ---")
            lines.append(result.stderr[:3000])

        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content="\n".join(lines),
            is_error=not result.success,
        )
