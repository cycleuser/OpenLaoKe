"""Execute HyperAuto tasks with tool calling support."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from openlaoke.core.hyperauto.executor import ToolExecutor
from openlaoke.core.hyperauto.types import SubTask

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


async def execute_task_with_tools(
    app_state: AppState,
    task: SubTask,
    original_request: str,
    max_iterations: int = 10,
    on_progress_callback: Any = None,
    workflow_context: Any = None,
) -> dict[str, Any]:
    """Execute a task using AI with tool calling capability."""
    from openlaoke.core.multi_provider_api import MultiProviderClient

    if app_state.multi_provider_config:
        api_client = MultiProviderClient(app_state.multi_provider_config)
        model = app_state.multi_provider_config.get_active_model()
    else:
        from openlaoke.types.providers import MultiProviderConfig

        config = MultiProviderConfig.defaults()
        api_client = MultiProviderClient(config)
        model = "gemma3:1b"

    executor = ToolExecutor(app_state)
    tool_schemas = await executor.get_tool_schemas()

    system_prompt = f"""You are an AI coding assistant. You have access to tools to complete tasks.

Your current task: {task.name}
Task description: {task.description}
Overall context: {original_request}

Instructions:
1. Use the available tools to complete this task
2. Make tool calls as needed - you can call multiple tools
3. After each tool call, you'll receive the result
4. Continue until the task is complete
5. Provide a summary when done

Available tools: {", ".join([t["name"] for t in tool_schemas[:10]])}"""

    messages = [
        {
            "role": "user",
            "content": f"Please complete this task using the available tools:\n\nTask: {task.name}\nDescription: {task.description}",
        }
    ]

    iteration = 0
    total_tokens = 0
    all_results: list[dict[str, Any]] = []

    while iteration < max_iterations:
        iteration += 1

        try:
            response_msg, token_usage, _ = await api_client.send_message(
                system_prompt=system_prompt,
                messages=messages,
                tools=tool_schemas,
                model=model,
                max_tokens=4000,
            )

            if token_usage:
                total_tokens += token_usage.total_tokens
                if workflow_context:
                    workflow_context.total_tokens += token_usage.total_tokens
                if on_progress_callback:
                    on_progress_callback(workflow_context)

            tool_uses = []
            if hasattr(response_msg, "tool_uses") and response_msg.tool_uses:
                tool_uses = response_msg.tool_uses

            tool_calls = []
            for tool_use in tool_uses:
                tool_calls.append(
                    {"name": tool_use.name, "input": tool_use.input, "id": tool_use.id}
                )

            if not tool_calls:
                final_text = ""
                if hasattr(response_msg, "content"):
                    if isinstance(response_msg.content, str):
                        final_text = response_msg.content
                    elif hasattr(response_msg.content, "text"):
                        final_text = response_msg.content.text

                return {
                    "success": True,
                    "iterations": iteration,
                    "tokens": total_tokens,
                    "tool_results": all_results,
                    "final_response": final_text,
                }

            for tool_call in tool_calls:
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get("name") or tool_call.get("function", {}).get(
                        "name", ""
                    )
                    tool_input = tool_call.get("input") or tool_call.get("function", {}).get(
                        "arguments", {}
                    )
                else:
                    tool_name = getattr(tool_call, "name", "")
                    tool_input = getattr(tool_call, "input", getattr(tool_call, "arguments", {}))

                if isinstance(tool_input, str):
                    try:
                        tool_input = json.loads(tool_input)
                    except json.JSONDecodeError:
                        tool_input = {}

                result = await executor.execute_tool(tool_name, tool_input)

                result_text = (
                    result.content
                    if isinstance(result.content, str)
                    else json.dumps(result.content)
                )

                all_results.append(
                    {
                        "tool": tool_name,
                        "input": tool_input,
                        "result": result_text[:1000],
                        "is_error": result.is_error,
                    }
                )

                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": f"call_{iteration}_{tool_name}",
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": json.dumps(tool_input),
                                },
                            }
                        ],
                    }
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": f"call_{iteration}_{tool_name}",
                        "content": result_text[:2000],
                    }
                )

        except Exception:
            break

    return {
        "success": True,
        "iterations": iteration,
        "tokens": total_tokens,
        "tool_results": all_results,
        "completed": iteration >= max_iterations,
    }
