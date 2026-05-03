"""/memory command for viewing, searching, and managing memories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.table import Table

from openlaoke.core.memory import get_memory_manager


@dataclass
class MemoryCommandResult:
    message: str = ""
    should_exit: bool = False
    should_clear: bool = False


class MemoryCommand:
    name = "memory"
    description = "View, search, and manage persistent memories (like Hermes agent)"
    aliases = ["mem", "回忆", "memory"]
    hidden = False

    async def execute(self, ctx: Any) -> MemoryCommandResult:
        args = ctx.args.strip() if hasattr(ctx, "args") else ""
        mgr = get_memory_manager()
        mgr.load()

        console = Console(force_terminal=True)

        if not args or args == "list":
            return self._list_all(mgr, console)

        if args.startswith("search "):
            query = args[7:].strip()
            return self._search(mgr, console, query)

        if args == "corrections":
            return self._show_type(mgr, console, "corrections")

        if args == "preferences":
            return self._show_type(mgr, console, "preferences")

        if args == "lessons":
            return self._show_type(mgr, console, "lessons")

        if args.startswith("add "):
            content = args[4:].strip()
            entry = mgr.add_correction(content)
            return MemoryCommandResult(
                message=f"[green]Memory added:[/] {entry.content}"
            )

        if args.startswith("remove "):
            entry_id = args[7:].strip()
            removed = mgr._store.remove(entry_id)
            if removed:
                return MemoryCommandResult(message=f"[green]Memory {entry_id} removed[/]")
            return MemoryCommandResult(message=f"[red]Memory {entry_id} not found[/]")

        return MemoryCommandResult(
            message=(
                "[bold]/memory[/] — Persistent Memory Manager\n"
                "  /memory list          — Show all memories\n"
                "  /memory search <q>    — Search memories\n"
                "  /memory corrections   — Show corrections\n"
                "  /memory preferences   — Show preferences\n"
                "  /memory lessons       — Show lessons learned\n"
                "  /memory add <text>    — Add a memory\n"
                "  /memory remove <id>   — Remove a memory"
            ),
        )

    def _list_all(self, mgr: Any, console: Console) -> MemoryCommandResult:
        entries = mgr._store.get_recent(20)
        if not entries:
            return MemoryCommandResult(message="[dim]No memories stored yet.[/]")

        table = Table(title="Memories")
        table.add_column("Type", style="cyan")
        table.add_column("Content", style="white")
        table.add_column("Confidence", style="green")
        table.add_column("Hits", style="dim")

        for entry in entries:
            table.add_row(
                str(entry.memory_type),
                entry.content[:80],
                f"{entry.confidence:.0%}",
                str(entry.hit_count),
            )

        with console.capture() as capture:
            console.print(table)
        return MemoryCommandResult(message=capture.get())

    def _search(self, mgr: Any, console: Console, query: str) -> MemoryCommandResult:
        results = mgr.search(query)
        memories = results.get("memories", [])
        sessions = results.get("sessions", [])

        lines: list[str] = [f"[bold]Memory search: {query}[/]"]
        if memories:
            lines.append(f"\n[bold]Memories ({len(memories)}):[/]")
            for m in memories[:10]:
                lines.append(f"  [{m['memory_type']}] {m['content'][:80]}")
        if sessions:
            lines.append(f"\n[bold]Sessions ({len(sessions)}):[/]")
            for s in sessions[:5]:
                lines.append(f"  session_{s['session_id'][:8]} ({s['match_count']} matches)")

        return MemoryCommandResult(message="\n".join(lines))

    def _show_type(self, mgr: Any, console: Console, type_name: str) -> MemoryCommandResult:
        method = getattr(mgr, f"get_{type_name}")
        entries = method()
        if not entries:
            return MemoryCommandResult(message=f"[dim]No {type_name} stored.[/]")

        lines = [f"[bold]{type_name.title()}:[/]"]
        for entry in entries:
            lines.append(f"  • {entry.content}")
        return MemoryCommandResult(message="\n".join(lines))


def register_command() -> None:
    from openlaoke.commands.registry import register_command as reg

    reg(MemoryCommand())
