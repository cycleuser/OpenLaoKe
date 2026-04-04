"""Agent runner for sub-agent tasks."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openlaoke.core.state import AppState
    from openlaoke.types.core_types import TaskState


async def run_subagent(
    prompt: str,
    description: str,
    app_state: AppState,
    task_state: TaskState,
) -> str:
    """Run a sub-agent with the given prompt.

    The sub-agent uses the same API configuration and tools as the parent,
    but with its own isolated conversation context.
    """
    from openlaoke.core.config_wizard import get_proxy_url
    from openlaoke.core.multi_provider_api import MultiProviderClient
    from openlaoke.core.tool import ToolRegistry
    from openlaoke.tools import register_all_tools

    registry = ToolRegistry()
    register_all_tools(registry)

    config = app_state.multi_provider_config
    if not config or not config.is_configured():
        return "Sub-agent error: No provider configured"

    app_config = getattr(app_state, "app_config", None)
    proxy = get_proxy_url(app_config) if app_config else None

    api = MultiProviderClient(config, proxy=proxy)

    system_prompt = _build_system_prompt(app_state)

    messages = [{"role": "user", "content": prompt}]
    tools = registry.get_all_for_prompt()

    max_iterations = 50
    iteration = 0
    result_parts = []

    try:
        while iteration < max_iterations:
            iteration += 1

            response, usage, cost = await api.send_message(
                system_prompt=system_prompt,
                messages=messages,
                tools=tools if iteration < max_iterations - 1 else None,
                model=app_state.session_config.model,
            )

            app_state.accumulate_tokens(usage)
            app_state.accumulate_cost(cost)

            if response.content:
                result_parts.append(response.content)

            messages.append(
                {
                    "role": "assistant",
                    "content": response.content,
                }
            )

            if not response.tool_uses:
                break

            for tool_use in response.tool_uses:
                tool = registry.get(tool_use.name)
                if not tool:
                    messages.append(
                        {
                            "role": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": f"Unknown tool: {tool_use.name}",
                        }
                    )
                    continue

                from openlaoke.core.tool import ToolContext

                ctx = ToolContext(
                    app_state=app_state,
                    tool_use_id=tool_use.id,
                )

                validation = tool.validate_input(tool_use.input)
                if not validation.result:
                    messages.append(
                        {
                            "role": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": f"Validation error: {validation.message}",
                        }
                    )
                    continue

                result = await tool.call(ctx, **tool_use.input)
                messages.append(
                    {
                        "role": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result.content
                        if isinstance(result.content, str)
                        else str(result.content),
                    }
                )

    except asyncio.CancelledError:
        raise
    except Exception as e:
        return f"Sub-agent error: {e}"
    finally:
        await api.close()

    return "\n".join(result_parts) if result_parts else "(no output)"


def _build_system_prompt(app_state: AppState) -> str:
    return (
        "You are a helpful assistant working as a sub-agent. "
        "You have access to tools to help accomplish tasks. "
        "Be concise and focused on the task at hand.\n\n"
        f"Working directory: {app_state.get_cwd()}"
    )
