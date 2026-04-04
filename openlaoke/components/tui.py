"""Textual TUI for OpenLaoKe - rich terminal interface."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Label, RichLog

from openlaoke.core.state import AppState
from openlaoke.utils.theme import ThemeManager


class MessagesLog(Vertical):
    """Scrollable message display area."""

    def __init__(self, theme_manager: ThemeManager, id: str | None = None) -> None:
        super().__init__(id=id)
        self.theme_manager = theme_manager

    def compose(self) -> ComposeResult:
        self.rich_log = RichLog(markup=True, wrap=True, highlight=True)
        yield self.rich_log

    def add_message(self, role: str, content: str) -> None:
        theme = self.theme_manager.current_theme
        if role == "user":
            self.rich_log.write(
                f"\n[{theme.colors.primary} bold]You:[/{theme.colors.primary} bold] {content}"
            )
        elif role == "assistant":
            self.rich_log.write(
                f"\n[{theme.colors.secondary} bold]OpenLaoKe:[/{theme.colors.secondary} bold] {content}"
            )
        elif role == "system":
            self.rich_log.write(f"[{theme.colors.muted}]{content}[/{theme.colors.muted}]")
        elif role == "error":
            self.rich_log.write(
                f"[{theme.colors.error} bold]Error: {content}[/{theme.colors.error} bold]"
            )
        elif role == "tool":
            self.rich_log.write(f"  [{theme.colors.muted}]{content}[/{theme.colors.muted}]")


class StatusBar(Horizontal):
    """Status bar showing session info."""

    def __init__(
        self, app_state: AppState, theme_manager: ThemeManager, id: str | None = None
    ) -> None:
        super().__init__(id=id)
        self.app_state = app_state
        self.theme_manager = theme_manager

    def compose(self) -> ComposeResult:
        self.model_label = Label(f"Model: {self.app_state.session_config.model}")
        self.cost_label = Label("Cost: $0.0000")
        self.tokens_label = Label("Tokens: 0")
        self.cwd_label = Label(f"CWD: {self.app_state.get_cwd()}")
        yield self.model_label
        yield self.cost_label
        yield self.tokens_label
        yield self.cwd_label

    def update_status(self) -> None:
        usage = self.app_state.token_usage
        cost = self.app_state.cost_info
        self.cost_label.update(f"Cost: ${cost.total_cost:.4f}")
        self.tokens_label.update(f"Tokens: {usage.total_tokens:,}")


class OpenLaoKeTUI(App):
    """Full TUI for OpenLaoKe."""

    def __init__(self, app_state: AppState) -> None:
        super().__init__()
        self.app_state = app_state
        self.theme_manager = ThemeManager(app_state.theme)

    def _generate_css(self) -> str:
        theme = self.theme_manager.current_theme
        return f"""
    Screen {{
        layout: vertical;
    }}
    #header-bar {{
        height: 3;
        dock: top;
        background: {theme.colors.background};
        color: {theme.colors.foreground};
    }}
    #messages-area {{
        height: 1fr;
        background: {theme.colors.background};
        color: {theme.colors.foreground};
    }}
    #input-bar {{
        height: 3;
        dock: bottom;
        background: {theme.colors.background};
        color: {theme.colors.foreground};
    }}
    Input {{
        width: 100%;
        border: solid {theme.colors.primary};
    }}
    Input:focus {{
        border: solid {theme.colors.accent};
    }}
    Label {{
        color: {theme.colors.foreground};
    }}
    Footer {{
        background: {theme.colors.background};
        color: {theme.colors.foreground};
    }}
    Header {{
        background: {theme.colors.primary};
        color: {theme.colors.background};
    }}
    """

    CSS = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield StatusBar(self.app_state, self.theme_manager)
        yield MessagesLog(self.theme_manager)
        yield Input(placeholder="Type a message or /help for commands...", id="prompt-input")
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#prompt-input", Input).focus()
        messages_log = self.query_one(MessagesLog)
        messages_log.add_message("system", "OpenLaoKe ready. Type a message to start.")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_input = event.value.strip()
        if not user_input:
            return

        event.input.value = ""

        messages_log = self.query_one(MessagesLog)
        messages_log.add_message("user", user_input)

        if user_input.startswith("/"):
            await self._handle_command(user_input[1:])
        else:
            await self._handle_chat(user_input)

    async def _handle_command(self, cmd_text: str) -> None:
        from openlaoke.commands.base import CommandContext
        from openlaoke.commands.registry import get_command

        messages_log = self.query_one(MessagesLog)

        parts = cmd_text.split(" ", 1)
        name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        command = get_command(name)
        if not command:
            messages_log.add_message("error", f"Unknown command: /{name}")
            return

        ctx = CommandContext(app_state=self.app_state, args=args)
        result = await command.execute(ctx)

        if result.message:
            messages_log.add_message("system", result.message)

        if result.should_exit:
            self.exit()

    async def _handle_chat(self, user_input: str) -> None:
        from openlaoke.core.api import APIClient, APIConfig
        from openlaoke.core.system_prompt import build_system_prompt
        from openlaoke.core.tool import ToolContext, ToolRegistry
        from openlaoke.tools.register import register_all_tools
        from openlaoke.types.core_types import (
            MessageRole,
            UserMessage,
        )

        messages_log = self.query_one(MessagesLog)

        registry = ToolRegistry()
        register_all_tools(registry)

        config = APIConfig.from_env()
        config.model = self.app_state.session_config.model
        api = APIClient(config)

        user_msg = UserMessage(role=MessageRole.USER, content=user_input)
        self.app_state.add_message(user_msg)

        system_prompt = build_system_prompt(self.app_state, registry.get_all_for_prompt())
        messages = self._serialize_messages()
        tools = registry.get_all_for_prompt()

        try:
            response, usage, cost = await api.send_message(
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
            )

            self.app_state.accumulate_tokens(usage)
            self.app_state.accumulate_cost(cost)

            if response.content:
                messages_log.add_message("assistant", response.content)

            if response.tool_uses:
                for tool_use in response.tool_uses:
                    tool = registry.get(tool_use.name)
                    if not tool:
                        messages_log.add_message("system", f"Unknown tool: {tool_use.name}")
                        continue

                    ctx = ToolContext(app_state=self.app_state, tool_use_id=tool_use.id)
                    result = await tool.call(ctx, **tool_use.input)
                    messages_log.add_message("tool", f"{tool_use.name}: {result.content[:200]}")

        except Exception as e:
            messages_log.add_message("error", str(e))
        finally:
            await api.close()

        self.query_one(StatusBar).update_status()

    def _serialize_messages(self) -> list[dict]:
        result = []
        for msg in self.app_state.get_messages():
            d = msg.to_dict()
            if d.get("type") == "user":
                result.append({"role": "user", "content": d.get("content", "")})
            elif d.get("type") == "assistant":
                content = []
                if d.get("content"):
                    content.append({"type": "text", "text": d["content"]})
                result.append({"role": "assistant", "content": content})
        return result
