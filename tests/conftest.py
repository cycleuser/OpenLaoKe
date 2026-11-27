"""Shared test fixtures / configuration for OpenLaoKe."""

from __future__ import annotations

import os
import tempfile

import pytest

from openlaoke.core.state import create_app_state
from openlaoke.core.tool import ToolContext


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture(autouse=True)
def _isolated_side_effect_dirs(tmp_path, monkeypatch):
    """Keep audit logs and stored tool output out of the developer's home.

    Both are written whenever a tool runs, so without this the suite would
    append to ``~/.openlaoke/audit`` and create artifacts for every fabricated
    tool call.
    """
    monkeypatch.setenv("OPENLAOKE_AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.setenv("OPENLAOKE_ARTIFACT_DIR", str(tmp_path / "artifacts"))


@pytest.fixture
def app_state():
    import openlaoke

    project_root = os.path.dirname(os.path.dirname(openlaoke.__file__))
    return create_app_state(cwd=project_root)


@pytest.fixture
def ctx(app_state):
    return ToolContext(app_state=app_state, tool_use_id="test_1")


def ctx_for_dir(work_dir: str) -> ToolContext:
    state = create_app_state(cwd=work_dir)
    return ToolContext(app_state=state, tool_use_id="test_1")
