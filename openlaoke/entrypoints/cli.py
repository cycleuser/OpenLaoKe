"""CLI entry point for OpenLaoKe."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

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
    known_subcommands: set[str] = set()
    prompt_parts: list[str] = []
    filtered_argv: list[str] = []
    args_iter = iter(sys.argv[1:])
    subcommand: str | None = None

    for tok in args_iter:
        if tok in known_subcommands and subcommand is None:
            subcommand = tok
            filtered_argv.append(tok)
        elif tok.startswith("-"):
            filtered_argv.append(tok)
            if tok in (
                "-m",
                "--model",
                "-p",
                "--permission",
                "-c",
                "--cwd",
                "--provider",
                "--api-key",
                "--base-url",
                "--proxy",
                "--max-tokens",
                "--thinking-budget",
                "--cors",
                "--bot",
                "--room",
            ):
                val = next(args_iter, "")
                if val:
                    filtered_argv.append(val)
        elif subcommand is None:
            prompt_parts.append(tok)
        else:
            filtered_argv.append(tok)

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
        default=None,
        help="AI provider to use (any configured key, e.g. deepseek, ollama_cloud, openai)",
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
        "--caveman",
        action="store_true",
        default=None,
        help="Enable caveman mode (concise output, no pleasantries)",
    )
    parser.add_argument(
        "--no-caveman",
        action="store_true",
        dest="no_caveman",
        help="Disable caveman mode",
    )
    parser.add_argument(
        "--max-tool-history",
        type=int,
        default=4096,
        help="Max bytes per tool result in LLM history (default: 4096)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=100,
        help="Max agent steps per turn (default: 100)",
    )
    parser.add_argument(
        "--all-tools",
        action="store_true",
        help=(
            "Headless runs: expose the full tool set (web, panel, swarm, memory, ...) "
            "instead of the focused core coding tools."
        ),
    )
    parser.add_argument(
        "--bot",
        default=None,
        help="Send the prompt to a named bot (bot mode)",
    )
    parser.add_argument(
        "--room",
        default=None,
        help="Send the prompt to a bot group room (implies --bot mode)",
    )

    args = parser.parse_args(filtered_argv)
    args.prompt = " ".join(prompt_parts) if prompt_parts else None

    console = Console(force_terminal=True)

    config = load_config()

    if args.show_config:
        show_current_config(config)
        return

    if args.config or config.first_run or not config.providers.has_provider_selected():
        config = run_config_wizard(config)
        config.first_run = False
        save_config(config)
        if args.config:
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

    # Handle --caveman / --no-caveman
    if args.caveman is True:
        app_state.caveman_mode = True
    elif args.no_caveman:
        app_state.caveman_mode = False
    if args.max_tool_history:
        app_state.max_tool_history = args.max_tool_history
    if args.max_steps:
        app_state.max_steps = args.max_steps
    app_state.use_all_tools = args.all_tools

    app_state.multi_provider_config = config.providers
    app_state.app_config = config

    if args.bot or args.room:
        if not args.prompt:
            console.print("[bold red]--bot/--room needs a prompt to send.[/bold red]")
            sys.exit(2)
        asyncio.run(_run_bot_prompt(args.prompt, app_state, config, args.bot, args.room))
    elif args.prompt:
        asyncio.run(_run_non_interactive(args.prompt, app_state, config))
    else:
        asyncio.run(_run_interactive(app_state, config))


async def _run_interactive(app_state, config) -> None:
    repl = REPL(app_state)
    repl.app_config = config
    await repl.run()


async def _run_bot_prompt(
    prompt: str,
    app_state,
    config,
    bot: str | None,
    room: str | None,
) -> None:
    from openlaoke.core.bot_mode import get_bot_mode, slug

    console = Console()
    mode = get_bot_mode(app_state)
    try:
        if room:
            turns = await mode.room_send(room, prompt)
            if not turns:
                console.print("(nobody in the room had anything to add)")
            for turn in turns:
                print(f"@{slug(turn.member)}: {turn.text}")
        else:
            assert bot is not None
            reply = await mode.ask(bot, prompt)
            print(reply or "(the bot stayed silent)")
        for item in await mode.drain():
            print(
                f"🔔 @{slug(item['bot'])} <- @{slug(item['from'])}: "
                f"{item.get('reply') or '(stayed silent)'}"
            )
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        sys.exit(1)

    print(f"\n--- Session cost: ${app_state.cost_info.total_cost:.4f} ---")


async def _run_non_interactive(prompt: str, app_state, config) -> None:
    from openlaoke.core.engine import STOP_ERROR, EnginePolicy, run_loop
    from openlaoke.core.system_prompt import build_system_prompt
    from openlaoke.core.tool import ToolRegistry
    from openlaoke.tools.register import register_all_tools, register_core_tools
    from openlaoke.types.core_types import MessageRole, UserMessage

    console = Console()

    registry = ToolRegistry()
    if getattr(app_state, "use_all_tools", False):
        register_all_tools(registry)
    else:
        register_core_tools(registry)

    proxy_url = get_proxy_url(config)
    api = MultiProviderClient(config.providers, proxy=proxy_url)

    app_state.add_message(UserMessage(role=MessageRole.USER, content=prompt))

    system_prompt = build_system_prompt(app_state, registry.get_all_for_prompt())
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

    policy = EnginePolicy(
        max_iterations=50,
        tools=registry.get_all_for_prompt(),
        on_text=lambda text: print(text),
    )

    try:
        result = await run_loop(
            app_state=app_state,
            api=api,
            registry=registry,
            system_prompt=system_prompt,
            messages=messages,
            policy=policy,
            send_kwargs={"max_tokens": config.max_tokens, "temperature": config.temperature},
        )
    finally:
        await api.close()

    if result.stop_reason == STOP_ERROR:
        console.print(f"\n[bold red]Error:[/bold red] {result.error}")
        sys.exit(1)

    if os.environ.get("OPENLAOKE_STATS"):
        usage = app_state.token_usage
        print(
            f"[stats] steps={result.iterations} "
            f"input_tokens={usage.input_tokens} output_tokens={usage.output_tokens}"
        )

    print(f"\n--- Session cost: ${app_state.cost_info.total_cost:.4f} ---")


if __name__ == "__main__":
    main()
