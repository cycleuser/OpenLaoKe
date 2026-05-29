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
