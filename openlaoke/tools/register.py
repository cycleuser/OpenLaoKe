"""Tool registration."""

from __future__ import annotations

from openlaoke.core.tool import ToolRegistry


def register_all_tools(registry: ToolRegistry) -> None:
    """Register all built-in tools."""
    from openlaoke.tools.agent_tool import register as register_agent
    from openlaoke.tools.bash_tool import register as register_bash
    from openlaoke.tools.edit_tool import register as register_edit
    from openlaoke.tools.glob_tool import register as register_glob
    from openlaoke.tools.grep_tool import register as register_grep
    from openlaoke.tools.notebook_write_tool import register as register_notebook
    from openlaoke.tools.read_tool import register as register_read
    from openlaoke.tools.taskkill_tool import register as register_taskkill
    from openlaoke.tools.write_tool import register as register_write

    register_bash(registry)
    register_read(registry)
    register_write(registry)
    register_edit(registry)
    register_glob(registry)
    register_grep(registry)
    register_agent(registry)
    register_taskkill(registry)
    register_notebook(registry)
