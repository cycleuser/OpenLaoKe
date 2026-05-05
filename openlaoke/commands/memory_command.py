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
    description = "View, search, and manage persistent memories (cross-session, SQLite-backed)"
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

        if args.startswith("recall "):
            query = args[7:].strip()
            return self._recall(mgr, console, query)

        if args == "corrections":
            return self._show_type(mgr, console, "corrections")

        if args == "preferences":
            return self._show_type(mgr, console, "preferences")

        if args == "lessons":
            return self._show_type(mgr, console, "lessons")

        if args.startswith("add "):
            content = args[4:].strip()
            entry = mgr.add_correction(content)
            return MemoryCommandResult(message=f"[green]Memory added:[/] {entry.content}")

        if args.startswith("remove "):
            entry_id = args[7:].strip()
            removed = mgr._store.remove(entry_id)
            if removed:
                return MemoryCommandResult(message=f"[green]Memory {entry_id} removed[/]")
            return MemoryCommandResult(message=f"[red]Memory {entry_id} not found[/]")

        if args.startswith("timeline"):
            parts = args.split()
            session_id = parts[1] if len(parts) > 1 else ""
            return self._timeline(mgr, console, session_id)

        if args == "stats":
            return self._stats(mgr, console)

        if args.startswith("type "):
            memory_type = args[5:].strip()
            return self._search_by_type(mgr, console, memory_type)

        return MemoryCommandResult(
            message=(
                "[bold]/memory[/] — Persistent Memory Manager (SQLite + FTS5)\n"
                "  /memory list              — Show all memories\n"
                "  /memory search <q>        — Search memories (legacy + SQLite)\n"
                "  /memory recall <q>        — Hybrid search (BM25 + vector + graph)\n"
                "  /memory type <type>       — List memories by type\n"
                "  /memory timeline [session]— Show event timeline\n"
                "  /memory stats             — Show memory statistics\n"
                "  /memory corrections       — Show corrections\n"
                "  /memory preferences       — Show preferences\n"
                "  /memory lessons           — Show lessons learned\n"
                "  /memory add <text>        — Add a memory\n"
                "  /memory remove <id>       — Remove a memory"
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
        sqlite_memories = results.get("sqlite_memories", [])
        sessions = results.get("sessions", [])

        lines: list[str] = [f"[bold]Memory search: {query}[/]"]
        if sqlite_memories:
            lines.append(f"\n[bold]SQLite Memories ({len(sqlite_memories)}):[/]")
            for m in sqlite_memories[:10]:
                lines.append(
                    f"  [{m['memory_type']}] (score: {m.get('score', 0):.2f}) {m['content'][:80]}"
                )
        if memories:
            lines.append(f"\n[bold]Legacy Memories ({len(memories)}):[/]")
            for m in memories[:10]:
                lines.append(f"  [{m['memory_type']}] {m['content'][:80]}")
        if sessions:
            lines.append(f"\n[bold]Sessions ({len(sessions)}):[/]")
            for s in sessions[:5]:
                lines.append(f"  session_{s['session_id'][:8]} ({s['match_count']} matches)")

        return MemoryCommandResult(message="\n".join(lines))

    def _recall(self, mgr: Any, console: Console, query: str) -> MemoryCommandResult:
        results = mgr.recall(query, limit=10)
        if not results:
            return MemoryCommandResult(message=f"[dim]No memories found for: {query}[/]")

        lines = [f"[bold]Recall results for: {query}[/] ({len(results)} found)\n"]
        for i, m in enumerate(results, 1):
            lines.append(f"{i}. [{m['memory_type']}] (score: {m['score']:.2f})")
            lines.append(f"   {m['content'][:150]}")
            if m.get("tags"):
                lines.append(f"   Tags: {', '.join(m['tags'][:5])}")
            if m.get("source_session"):
                lines.append(f"   Session: {m['source_session'][:12]}")
            lines.append("")

        return MemoryCommandResult(message="\n".join(lines))

    def _timeline(self, mgr: Any, console: Console, session_id: str) -> MemoryCommandResult:
        events = mgr.get_timeline(session_id=session_id, limit=30)
        if not events:
            return MemoryCommandResult(message="[dim]No timeline events found.[/]")

        import time

        lines = [f"[bold]Timeline[/] ({len(events)} events)\n"]
        for event in events:
            ts = time.strftime("%H:%M:%S", time.localtime(event["created_at"]))
            lines.append(f"[{ts}] {event['event_type']}: {event['summary']}")

        return MemoryCommandResult(message="\n".join(lines))

    def _stats(self, mgr: Any, console: Console) -> MemoryCommandResult:
        stats = mgr.get_stats()
        if "error" in stats:
            return MemoryCommandResult(message=f"[red]{stats['error']}[/]")

        lines = [
            "[bold]Memory Statistics[/]\n",
            f"Total memories: {stats['total_memories']}",
            f"Total concepts: {stats['total_concepts']}",
            f"Timeline events: {stats['total_timeline_events']}",
            f"Database: {stats['db_path']}",
        ]
        if stats.get("memory_types"):
            lines.append("\nBy type:")
            for mtype, count in stats["memory_types"].items():
                lines.append(f"  {mtype}: {count}")

        return MemoryCommandResult(message="\n".join(lines))

    def _search_by_type(self, mgr: Any, console: Console, memory_type: str) -> MemoryCommandResult:
        results = mgr.recall("", limit=50)
        filtered = [m for m in results if m.get("memory_type") == memory_type]
        if not filtered:
            return MemoryCommandResult(message=f"[dim]No memories of type '{memory_type}'.[/]")

        lines = [f"[bold]Memories of type '{memory_type}'[/] ({len(filtered)})\n"]
        for i, m in enumerate(filtered[:20], 1):
            lines.append(f"{i}. (score: {m['score']:.2f}) {m['content'][:120]}")
            if m.get("tags"):
                lines.append(f"   Tags: {', '.join(m['tags'][:5])}")
            lines.append("")

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
    from openlaoke.commands.registry import _commands

    cmd = MemoryCommand()
    _commands[cmd.name] = cmd  # type: ignore[assignment]
