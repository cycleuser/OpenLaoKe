"""High-level commands the Controller accepts.

A frontend never reaches into the agent internals. It only issues one of
these high-level commands. The Controller translates them into async
agent turns and emits the result as events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ControllerCommand:
    """A typed command for the Controller."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""


@dataclass
class SubmitCommand(ControllerCommand):
    """Submit a raw user input string for the next turn."""

    name: str = "submit"
    text: str = ""

    def __init__(self, text: str, session_id: str = "") -> None:
        super().__init__(name="submit", args={"text": text}, session_id=session_id)
        self.text = text


@dataclass
class CancelCommand(ControllerCommand):
    name: str = "cancel"


@dataclass
class ApproveCommand(ControllerCommand):
    name: str = "approve"
    decision: str = "allow"
    remember: bool = False
    target: str = ""


@dataclass
class SetPlanModeCommand(ControllerCommand):
    name: str = "set_plan_mode"
    enabled: bool = False


@dataclass
class CompactCommand(ControllerCommand):
    name: str = "compact"


@dataclass
class NewSessionCommand(ControllerCommand):
    name: str = "new_session"


@dataclass
class ResumeSessionCommand(ControllerCommand):
    name: str = "resume_session"
    target: str = ""


@dataclass
class RewindCommand(ControllerCommand):
    name: str = "rewind"
    target: int = 0
    scope: str = "code+conversation"


@dataclass
class ForkCommand(ControllerCommand):
    name: str = "fork"
    target: int | None = None
    label: str = ""


@dataclass
class BranchCommand(ControllerCommand):
    name: str = "branch"
    label: str = ""


@dataclass
class SwitchCommand(ControllerCommand):
    name: str = "switch"
    target: str = ""


@dataclass
class SummarizeFromCommand(ControllerCommand):
    name: str = "summarize_from"
    target: int = 0


@dataclass
class SummarizeUpToCommand(ControllerCommand):
    name: str = "summarize_up_to"
    target: int = 0


@dataclass
class AddMCPServerCommand(ControllerCommand):
    name: str = "add_mcp_server"
    plugin: dict[str, Any] = field(default_factory=dict)


@dataclass
class RemoveMCPServerCommand(ControllerCommand):
    name: str = "remove_mcp_server"
    server: str = ""


@dataclass
class ConnectMCPCommand(ControllerCommand):
    name: str = "connect_mcp"
    server: str = ""


@dataclass
class DisconnectMCPCommand(ControllerCommand):
    name: str = "disconnect_mcp"
    server: str = ""


@dataclass
class SetBypassCommand(ControllerCommand):
    name: str = "set_bypass"
    enabled: bool = False


@dataclass
class ForgetMemoryCommand(ControllerCommand):
    name: str = "forget_memory"
    fact_id: str = ""


@dataclass
class QuickAddCommand(ControllerCommand):
    name: str = "quick_add"
    note: str = ""


@dataclass
class SaveDocCommand(ControllerCommand):
    name: str = "save_doc"
    text: str = ""
    target: str = "project"


COMMAND_TYPES: dict[str, type[ControllerCommand]] = {
    "submit": SubmitCommand,
    "cancel": CancelCommand,
    "approve": ApproveCommand,
    "set_plan_mode": SetPlanModeCommand,
    "compact": CompactCommand,
    "new_session": NewSessionCommand,
    "resume_session": ResumeSessionCommand,
    "rewind": RewindCommand,
    "fork": ForkCommand,
    "branch": BranchCommand,
    "switch": SwitchCommand,
    "summarize_from": SummarizeFromCommand,
    "summarize_up_to": SummarizeUpToCommand,
    "add_mcp_server": AddMCPServerCommand,
    "remove_mcp_server": RemoveMCPServerCommand,
    "connect_mcp": ConnectMCPCommand,
    "disconnect_mcp": DisconnectMCPCommand,
    "set_bypass": SetBypassCommand,
    "forget_memory": ForgetMemoryCommand,
    "quick_add": QuickAddCommand,
    "save_doc": SaveDocCommand,
}


def parse_command(name: str, args: dict[str, Any] | None = None) -> ControllerCommand:
    """Build a typed command from name + args dict (useful for HTTP/JSON)."""
    cls = COMMAND_TYPES.get(name, ControllerCommand)
    cmd = cls(args=args or {})
    return cmd
