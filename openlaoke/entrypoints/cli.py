"""CLI entry point for OpenLaoKe."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from rich.console import Console

from openlaoke import __version__
from openlaoke.core.config_wizard import (
    get_proxy_url,
    run_config_wizard,
    show_current_config,
)
from openlaoke.core.multi_provider_api import MultiProviderClient
from openlaoke.core.repl import REPL
from openlaoke.core.state import create_app_state
from openlaoke.utils.config import load_config, save_config


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="openlaoke",
        description="OpenLaoKe - Open-source AI coding assistant",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"OpenLaoKe {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    server_parser = subparsers.add_parser("server", help="Start HTTP API server")
    server_parser.add_argument(
        "--host",
        default="localhost",
        help="Server host (default: localhost)",
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=3000,
        help="Server port (default: 3000)",
    )
    server_parser.add_argument(
        "--cors",
        nargs="*",
        default=None,
        help="Additional CORS origins",
    )

    parser.add_argument(
        "-m",
        "--model",
        default=None,
        help="Model to use (e.g., gpt-4o, llama3.2, gemma3:1b)",
    )
    parser.add_argument(
        "-p",
        "--permission",
        choices=["default", "auto", "bypass"],
        default=None,
        help="Permission mode (auto/bypass = no confirmations)",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Auto-approve all tool calls (same as --permission auto)",
    )
    parser.add_argument(
        "-c",
        "--cwd",
        default=None,
        help="Working directory",
    )
    parser.add_argument(
        "--provider",
        choices=[
            "anthropic",
            "openai",
            "minimax",
            "aliyun_coding_plan",
            "ollama",
            "lm_studio",
            "openai_compatible",
        ],
        default=None,
        help="AI provider to use",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key for the provider",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="API base URL (for local/custom providers)",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help="Proxy URL (e.g., http://127.0.0.1:7890)",
    )
    parser.add_argument(
        "--no-proxy",
        action="store_true",
        help="Disable proxy",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Maximum tokens in response",
    )
    parser.add_argument(
        "--thinking-budget",
        type=int,
        default=None,
        help="Thinking budget tokens",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--config",
        action="store_true",
        help="Run configuration wizard",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Show current configuration",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Enable local mode (for small local models with atomic decomposition, multi-model coordination)",
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Direct prompt to execute (non-interactive mode)",
    )

    args = parser.parse_args()

    console = Console(force_terminal=True)

    if args.command == "server":
        from openlaoke.server import Server

        server = Server(
            host=args.host,
            port=args.port,
            cors_origins=args.cors,
        )
        console.print(f"[green]Starting OpenLaoKe server on {args.host}:{args.port}[/green]")
        server.run()
        return

    config = load_config()

    if args.show_config:
        show_current_config(config)
        return

    if args.config or config.first_run or not config.providers.is_configured():
        config = run_config_wizard(config)
        save_config(config)
        if not args.config:
            console.print("\n[dim]Run 'openlaoke' to start chatting.[/dim]")
            return

    # Apply command-line overrides
    if args.provider:
        if args.provider in config.providers.providers:
            config.providers.active_provider = args.provider
        else:
            console.print(f"[red]Unknown provider: {args.provider}[/red]")
            return

    if args.api_key:
        provider = config.providers.get_active_provider()
        if provider:
            provider.api_key = args.api_key

    if args.base_url:
        provider = config.providers.get_active_provider()
        if provider:
            provider.base_url = args.base_url

    if args.model:
        config.providers.active_model = args.model

    if args.no_proxy:
        config.proxy_mode = "none"
        config.proxy_url = ""
    elif args.proxy:
        config.proxy_mode = "custom"
        config.proxy_url = args.proxy

    cwd = args.cwd or os.getcwd()

    persist_dir = os.path.expanduser("~/.openlaoke/sessions")
    os.makedirs(persist_dir, exist_ok=True)
    persist_path = os.path.join(persist_dir, f"session_{int(__import__('time').time())}.json")

    app_state = create_app_state(
        cwd=cwd,
        model=config.providers.get_active_model(),
        persist_path=persist_path,
    )
    app_state.session_config.model = config.providers.get_active_model()

    if config.auto_approve_all:
        from openlaoke.types.core_types import PermissionMode

        app_state.permission_config.mode = PermissionMode.AUTO
        app_state.auto_accept = True

    if args.max_tokens:
        config.max_tokens = args.max_tokens
    if args.thinking_budget:
        config.thinking_budget = args.thinking_budget
    if args.permission:
        from openlaoke.types.core_types import PermissionMode

        app_state.permission_config.mode = PermissionMode(args.permission)
    if args.yes:
        from openlaoke.types.core_types import PermissionMode

        app_state.permission_config.mode = PermissionMode.AUTO
        app_state.auto_accept = True
    if args.verbose:
        app_state.verbose = True
    if args.local:
        app_state.local_mode = True

    app_state.multi_provider_config = config.providers
    app_state.app_config = config

    if args.prompt:
        prompt_text = " ".join(args.prompt)
        asyncio.run(_run_non_interactive(prompt_text, app_state, config))
    else:
        asyncio.run(_run_interactive(app_state, config))


async def _run_interactive(app_state, config) -> None:
    repl = REPL(app_state)
    repl.app_config = config
    await repl.run()


async def _run_non_interactive(prompt: str, app_state, config) -> None:
    from openlaoke.core.system_prompt import build_system_prompt
    from openlaoke.core.tool import ToolRegistry
    from openlaoke.tools.register import register_all_tools
    from openlaoke.types.core_types import MessageRole, UserMessage

    console = Console()

    registry = ToolRegistry()
    register_all_tools(registry)

    proxy_url = get_proxy_url(config)
    api = MultiProviderClient(config.providers, proxy=proxy_url)

    user_msg = UserMessage(role=MessageRole.USER, content=prompt)
    app_state.add_message(user_msg)

    system_prompt = build_system_prompt(app_state, registry.get_all_for_prompt())
    messages = [{"role": "user", "content": prompt}]
    tools = registry.get_all_for_prompt()

    max_iterations = 50
    iteration = 0

    try:
        while iteration < max_iterations:
            iteration += 1

            response, usage, cost = await api.send_message(
                system_prompt=system_prompt,
                messages=messages,
                tools=tools if iteration < max_iterations - 1 else None,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
            )

            app_state.accumulate_tokens(usage)
            app_state.accumulate_cost(cost)

            if response.content:
                print(response.content)

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

                ctx = ToolContext(app_state=app_state, tool_use_id=tool_use.id)

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

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        sys.exit(1)
    finally:
        await api.close()

    print(f"\n--- Session cost: ${app_state.cost_info.total_cost:.4f} ---")


if __name__ == "__main__":
    main()
