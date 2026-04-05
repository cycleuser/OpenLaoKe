"""Project scaffolding command for quick project setup."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from openlaoke.commands.base import CommandContext, CommandResult, SlashCommand
from openlaoke.core.code_templates import (
    PROJECT_TEMPLATES,
    ProjectType,
    get_template,
    suggest_template,
)


class ScaffoldCommand(SlashCommand):
    name = "scaffold"
    description = "Generate project scaffold from templates"
    aliases = ["new", "create", "init"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        """Execute scaffold command."""
        console = Console()

        args = ctx.args.strip()

        if not args or args in ["list", "ls"]:
            return self._list_templates(console)

        if args.startswith("suggest "):
            task = args[8:].strip()
            return self._suggest_templates(task, console)

        return self._create_project(args, console, ctx)

    def _list_templates(self, console: Console) -> CommandResult:
        """List all available templates."""
        table = Table(title="Available Project Templates")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Language", style="magenta")
        table.add_column("Description")

        for template_id, template in PROJECT_TEMPLATES.items():
            table.add_row(
                template_id,
                template.name,
                template.project_type.value,
                template.language.value,
                template.description[:50] + "..."
                if len(template.description) > 50
                else template.description,
            )

        console.print(table)

        return CommandResult(
            message="\n[dim]Usage: /scaffold <template_id> [project_name][/dim]\n"
            "[dim]Example: /scaffold python_cli_tool my_tool[/dim]"
        )

    def _suggest_templates(self, task: str, console: Console) -> CommandResult:
        """Suggest templates based on task description."""
        suggestions = suggest_template(task)

        if not suggestions:
            return CommandResult(
                message="[yellow]No matching templates found for this task.[/yellow]\n"
                "[dim]Use /scaffold list to see all available templates.[/dim]"
            )

        console.print(f"[green]Suggested templates for: {task}[/green]\n")

        for template_id in suggestions:
            template = get_template(template_id)
            if template:
                console.print(
                    Panel(
                        f"[bold]{template.name}[/bold]\n"
                        f"[dim]{template.description}[/dim]\n\n"
                        f"[cyan]Type:[/cyan] {template.project_type.value}\n"
                        f"[cyan]Language:[/cyan] {template.language.value}\n"
                        f"[cyan]Dependencies:[/cyan] {', '.join(template.dependencies[:3])}\n\n"
                        f"[yellow]Usage: /scaffold {template_id}[/yellow]",
                        title=template_id,
                        border_style="green",
                    )
                )

        return CommandResult(message="")

    def _create_project(self, args: str, console: Console, ctx: CommandContext) -> CommandResult:
        """Create a new project from template."""
        parts = args.split(maxsplit=1)

        template_id = parts[0]
        project_name = parts[1] if len(parts) > 1 else None

        template = get_template(template_id)
        if not template:
            return CommandResult(
                success=False,
                message=f"[red]Template not found: {template_id}[/red]\n"
                f"[dim]Use /scaffold list to see available templates.[/dim]",
            )

        if not project_name:
            project_name = f"my_{template.project_type.value}"

        project_dir = Path(ctx.app_state.cwd) / project_name

        if project_dir.exists():
            return CommandResult(
                success=False,
                message=f"[red]Directory already exists: {project_dir}[/red]\n"
                f"[dim]Choose a different project name or remove the existing directory.[/dim]",
            )

        console.print(f"\n[green]Creating project: {project_name}[/green]")
        console.print(f"[green]Template: {template.name}[/green]")
        console.print(f"[green]Location: {project_dir}[/green]\n")

        project_dir.mkdir(parents=True, exist_ok=True)

        for file_name, content in template.files.items():
            file_path = project_dir / file_name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            console.print(f"  [cyan]Created:[/cyan] {file_name}")

        if template.readme:
            readme_path = project_dir / "README.md"
            readme_path.write_text(template.readme)
            console.print("  [cyan]Created:[/cyan] README.md")

        if template.dependencies:
            requirements_path = project_dir / "requirements.txt"
            requirements_path.write_text("\n".join(template.dependencies))
            console.print("  [cyan]Created:[/cyan] requirements.txt")

        console.print("\n[bold green]✓ Project created successfully![/bold green]")

        console.print("\n[bold]Next steps:[/bold]")
        console.print(f"  1. cd {project_name}")

        if template.dependencies:
            console.print(
                f"  2. {template.setup_commands[0] if template.setup_commands else 'pip install -r requirements.txt'}"
            )

        if template.project_type == ProjectType.WEB_API:
            console.print("  3. uvicorn main:app --reload")
        elif template.project_type == ProjectType.CLI_TOOL:
            console.print("  3. python main.py --help")
        elif template.project_type == ProjectType.DATA_PROCESSING:
            console.print("  3. python processor.py --help")
        else:
            console.print("  3. python main.py")

        console.print(f"\n[dim]Total files: {len(template.files)}[/dim]")
        console.print(f"[dim]Dependencies: {len(template.dependencies)} packages[/dim]")

        return CommandResult(message=f"\n[dim]Project ready at: {project_dir.absolute()}[/dim]")


class KnowledgeDownloadCommand(SlashCommand):
    name = "download-knowledge"
    description = "Download documentation for knowledge base"
    aliases = ["dl-docs", "fetch-docs"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        """Execute knowledge download command."""
        from openlaoke.core.enhanced_knowledge_base import EnhancedKnowledgeBase

        console = Console()
        args = ctx.args.strip()

        if not args:
            return CommandResult(
                message="[yellow]Usage: /download-knowledge <source_or_task>[/yellow]\n"
                "[dim]Examples:[/dim]\n"
                "  [dim]/download-knowledge python[/dim]\n"
                "  [dim]/download-knowledge numpy[/dim]\n"
                "  [dim]/download-knowledge 'web api development'[/dim]\n"
                "  [dim]/download-knowledge list[/dim]"
            )

        if args == "list":
            from openlaoke.core.doc_sources import DOC_SOURCES

            table = Table(title="Available Documentation Sources")
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Category")
            table.add_column("URLs")

            for source_id, source_info in list(DOC_SOURCES.items())[:20]:
                table.add_row(
                    source_id,
                    source_info["name"],
                    source_info.get("category", "general"),
                    str(len(source_info["urls"])),
                )

            console.print(table)
            return CommandResult(
                message=f"\n[dim]Total: {len(DOC_SOURCES)} sources available[/dim]"
            )

        kb = EnhancedKnowledgeBase()

        console.print(f"[cyan]Downloading documentation for: {args}[/cyan]\n")

        try:
            num_chunks = kb.download_for_task(args)

            return CommandResult(
                message=f"\n[green]✓ Downloaded {num_chunks} knowledge chunks[/green]\n"
                f"[dim]Total knowledge base size: {len(kb.downloaded_chunks)} chunks[/dim]"
            )
        except Exception as e:
            return CommandResult(
                success=False, message=f"[red]Failed to download documentation: {e}[/red]"
            )


class QuickStartCommand(SlashCommand):
    name = "quickstart"
    description = "Quick start guide for common development tasks"
    aliases = ["qs", "guide"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        """Execute quickstart command."""
        console = Console()
        args = ctx.args.strip().lower()

        guides = {
            "cli": {
                "title": "CLI Tool Development",
                "steps": [
                    "1. Create project: /scaffold python_cli_tool my_tool",
                    "2. Install dependencies: cd my_tool && pip install click rich",
                    "3. Edit main.py to add your functionality",
                    "4. Test: python main.py --help",
                    "5. Install globally: pip install -e .",
                ],
                "knowledge": ["click", "argparse", "pathlib", "logging"],
            },
            "api": {
                "title": "Web API Development",
                "steps": [
                    "1. Create project: /scaffold python_web_api my_api",
                    "2. Install dependencies: cd my_api && pip install fastapi uvicorn",
                    "3. Define models in models.py",
                    "4. Add endpoints in main.py",
                    "5. Run: uvicorn main:app --reload",
                ],
                "knowledge": ["fastapi", "flask", "pydantic", "requests"],
            },
            "data": {
                "title": "Data Processing",
                "steps": [
                    "1. Create project: /scaffold python_data_processing my_pipeline",
                    "2. Install dependencies: pip install pandas numpy",
                    "3. Configure data sources in processor.py",
                    "4. Add custom processing logic",
                    "5. Run: python processor.py data.csv",
                ],
                "knowledge": ["pandas", "numpy", "multiprocessing", "pathlib"],
            },
            "test": {
                "title": "Testing",
                "steps": [
                    "1. Install pytest: pip install pytest pytest-cov",
                    "2. Create tests/ directory",
                    "3. Write test_*.py files",
                    "4. Use fixtures for common setup",
                    "5. Run: pytest tests/ -v",
                ],
                "knowledge": ["pytest", "unittest", "mock"],
            },
        }

        if not args or args not in guides:
            console.print("[bold]Available Quick Start Guides:[/bold]\n")
            for guide_id, guide in guides.items():
                console.print(f"  [cyan]/quickstart {guide_id}[/cyan] - {guide['title']}")
            return CommandResult(
                message="\n[dim]Use /quickstart <topic> to see detailed guide[/dim]"
            )

        guide = guides[args]

        console.print(
            Panel(
                "\n".join(guide["steps"]),
                title=f"[bold]{guide['title']}[/bold]",
                border_style="green",
            )
        )

        console.print("\n[bold]Recommended knowledge:[/bold]")
        for knowledge_id in guide["knowledge"]:
            console.print(f"  [cyan]/download-knowledge {knowledge_id}[/cyan]")

        return CommandResult(message="")
