"""Startup health checks.

Validates provider reachability, config integrity, and
environment readiness before the agent loop starts.
"""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    latency_ms: float = 0.0


@dataclass
class HealthReport:
    checks: list[CheckResult] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    @property
    def all_ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def errors(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.ok]

    def format(self) -> str:
        lines = ["Health check:", ""]
        for c in self.checks:
            icon = "✓" if c.ok else "✗"
            line = f"  {icon} {c.name}"
            if c.latency_ms > 0:
                line += f" ({c.latency_ms:.0f}ms)"
            if c.detail:
                line += f" — {c.detail}"
            lines.append(line)
        return "\n".join(lines)


async def run_health_checks(
    config: Any = None,
    check_providers: bool = True,
) -> HealthReport:
    """Run all startup checks.

    Checks performed:
    1. Python version >= 3.11
    2. Config file exists and is parseable
    3. At least one provider is configured
    4. Provider reachability (if check_providers=True)
    5. Git available
    """
    report = HealthReport()

    # 1. Python version
    py_version = sys.version_info[:2]
    ok_py = py_version >= (3, 11)
    report.checks.append(
        CheckResult(
            name="python_version",
            ok=ok_py,
            detail=f"Python {py_version[0]}.{py_version[1]}",
        )
    )

    # 2. Config
    if config is not None:
        report.checks.append(
            CheckResult(
                name="config",
                ok=True,
                detail=f"{len(getattr(config, 'providers', {}))} providers configured",
            )
        )

        # 3. Provider config
        providers = getattr(config, "providers", {})
        active = getattr(config, "active_provider", "")
        if active and active in providers:
            p = providers[active]
            report.checks.append(
                CheckResult(
                    name=f"provider_{active}",
                    ok=p.is_configured(),
                    detail=p.default_model or "no default model",
                )
            )
        else:
            report.checks.append(
                CheckResult(
                    name="provider_active",
                    ok=False,
                    detail=f"active_provider='{active}' not found in configured providers",
                )
            )
    else:
        report.checks.append(
            CheckResult(name="config", ok=False, detail="no config provided")
        )

    # 4. Provider reachability
    if check_providers and config is not None:
        try:
            from openlaoke.core.multi_provider_api import MultiProviderClient

            results = await MultiProviderClient.health_check(config, timeout=5.0)
            for name, result in results.items():
                report.checks.append(
                    CheckResult(
                        name=f"reachable_{name}",
                        ok=result.get("ok", False),
                        detail=str(result.get("note") or result.get("error") or f"status {result.get('status','?')}"),
                        latency_ms=result.get("latency_ms", 0),
                    )
                )
        except Exception as exc:
            report.checks.append(
                CheckResult(name="reachability", ok=False, detail=str(exc)[:200])
            )

    # 5. Git
    import shutil

    has_git = shutil.which("git") is not None
    report.checks.append(
        CheckResult(name="git", ok=has_git, detail="available" if has_git else "not found")
    )

    return report
