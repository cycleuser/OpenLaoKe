"""Tests for startup health checks (openlaoke.control.health)."""

from __future__ import annotations

import asyncio

from openlaoke.control.health import CheckResult, HealthReport, run_health_checks


class TestHealthReport:
    def test_all_ok_true_when_empty(self) -> None:
        assert HealthReport().all_ok is True

    def test_all_ok_false_with_failure(self) -> None:
        report = HealthReport(
            checks=[CheckResult(name="a", ok=True), CheckResult(name="b", ok=False)]
        )
        assert report.all_ok is False

    def test_errors_filters_failures(self) -> None:
        report = HealthReport(
            checks=[
                CheckResult(name="ok1", ok=True),
                CheckResult(name="bad", ok=False, detail="boom"),
            ]
        )
        errors = report.errors()
        assert len(errors) == 1
        assert errors[0].name == "bad"

    def test_format_renders_icons_and_detail(self) -> None:
        report = HealthReport(
            checks=[
                CheckResult(name="python", ok=True, latency_ms=12.0),
                CheckResult(name="config", ok=False, detail="no config"),
            ]
        )
        text = report.format()
        assert "Health check:" in text
        assert "✓ python" in text
        assert "12ms" in text
        assert "✗ config" in text
        assert "no config" in text


class _FakeProvider:
    def __init__(self, configured: bool = True, model: str = "m1") -> None:
        self._configured = configured
        self.default_model = model

    def is_configured(self) -> bool:
        return self._configured


class _FakeConfig:
    def __init__(self, providers: dict, active: str) -> None:
        self.providers = providers
        self.active_provider = active


class TestRunHealthChecks:
    def test_no_config_reports_failure(self) -> None:
        async def scenario() -> None:
            report = await run_health_checks(config=None, check_providers=False)
            names = {c.name: c for c in report.checks}
            assert names["python_version"].ok is True
            assert names["config"].ok is False
            assert names["git"].ok is True

        asyncio.run(scenario())

    def test_config_with_active_provider(self) -> None:
        async def scenario() -> None:
            cfg = _FakeConfig({"anthropic": _FakeProvider(True, "claude")}, "anthropic")
            report = await run_health_checks(config=cfg, check_providers=False)
            names = {c.name: c for c in report.checks}
            assert "provider_anthropic" in names
            assert names["provider_anthropic"].ok is True
            assert names["provider_anthropic"].detail == "claude"

        asyncio.run(scenario())

    def test_config_with_unconfigured_provider(self) -> None:
        async def scenario() -> None:
            cfg = _FakeConfig({"openai": _FakeProvider(False)}, "openai")
            report = await run_health_checks(config=cfg, check_providers=False)
            names = {c.name: c for c in report.checks}
            assert names["provider_openai"].ok is False

        asyncio.run(scenario())

    def test_config_with_missing_active_provider(self) -> None:
        async def scenario() -> None:
            cfg = _FakeConfig({"openai": _FakeProvider(True)}, "ghost")
            report = await run_health_checks(config=cfg, check_providers=False)
            names = {c.name: c for c in report.checks}
            assert names["provider_active"].ok is False
            assert "ghost" in names["provider_active"].detail

        asyncio.run(scenario())

    def test_check_providers_false_skips_reachability(self) -> None:
        async def scenario() -> None:
            cfg = _FakeConfig({"openai": _FakeProvider(True)}, "openai")
            report = await run_health_checks(config=cfg, check_providers=False)
            assert not any(c.name.startswith("reachable_") for c in report.checks)

        asyncio.run(scenario())
