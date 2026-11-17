"""MessageAgent - send a message from one bot to another bot's chat."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.bot_mode import BotMode, current_bot, get_bot_mode, slug
from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class MessageAgentInput(BaseModel):
    target: str = Field(description="Bot handle or name, for example @researcher")
    message: str = Field(description="What to tell that bot, in your own words")
    wait: bool = Field(
        default=False,
        description="Wait for the reply now instead of queueing it for the next drain",
    )


class MessageAgentTool(Tool):
    """Queue a message into a teammate bot's canonical chat."""

    name = "MessageAgent"
    description = (
        "Send a message to a teammate bot. By default the delivery is queued and the "
        "reply arrives later as a notification; set wait=true to run that bot now and "
        "get the answer in this turn. Only available inside a bot chat or room."
    )
    input_schema = MessageAgentInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = False

    def __init__(self, mode: BotMode | None = None) -> None:
        self._mode = mode

    def _resolve_mode(self, ctx: ToolContext) -> BotMode:
        return self._mode or get_bot_mode(ctx.app_state)

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        sender = current_bot()
        if not sender:
            return self._error(ctx, "Error: MessageAgent only works inside a bot chat or a room.")

        target = str(kwargs.get("target") or "").strip()
        message = str(kwargs.get("message") or "").strip()
        if not target:
            return self._error(ctx, "Error: target is required")
        if not message:
            return self._error(ctx, "Error: message is required")

        mode = self._resolve_mode(ctx)
        profile = mode.get_bot(target)
        if profile is None:
            roster = ", ".join("@" + slug(bot.name) for bot in mode.list_bots(include_hidden=True))
            return self._error(
                ctx,
                f"Error: no bot named '{target}'. Teammates: {roster or '(none)'}",
            )
        if slug(profile.name) == sender:
            return self._error(ctx, "Error: you cannot message yourself")

        wait = bool(kwargs.get("wait"))
        if wait and mode.is_busy(profile.name):
            return self._error(
                ctx,
                f"Error: @{slug(profile.name)} is mid-turn; send without wait to queue it.",
            )

        try:
            envelope = mode.enqueue(sender, profile.name, message)
        except ValueError as exc:
            return self._error(ctx, f"Error: {exc}")

        if not wait:
            pending = len(mode.inbox(profile.name))
            return self._result(
                ctx,
                f"Queued for @{slug(profile.name)} ({pending} pending). "
                "The reply will arrive after the current turn.",
            )

        reply = await mode.ask(profile.name, message, sender=sender)
        mode._update_inbox(profile, envelope, status="delivered", reply=reply)
        body = reply.strip() or "(no reply: the bot chose to stay silent)"
        return self._result(ctx, f"@{slug(profile.name)} replied:\n{body}")

    @staticmethod
    def _result(ctx: ToolContext, content: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=content)

    @staticmethod
    def _error(ctx: ToolContext, message: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=message, is_error=True)


def register(registry: ToolRegistry) -> None:
    registry.register(MessageAgentTool())


__all__ = ["MessageAgentInput", "MessageAgentTool", "register"]
