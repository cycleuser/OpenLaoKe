"""CLI commands for managing built-in GGUF models."""

from __future__ import annotations

import asyncio
import os

from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.prompt import Prompt
from rich.table import Table

from openlaoke.core.local_model_manager import DEFAULT_BUILTIN_MODELS, LocalModelManager

console = Console(force_terminal=True)


async def download_model(model_id: str | None = None) -> None:
    """Download a built-in model or any ModelScope GGUF model."""
    manager = LocalModelManager()

    # 检查是否是内置模型
    if model_id and model_id in DEFAULT_BUILTIN_MODELS:
        model = manager.get_model(model_id)
        if model and model.downloaded:
            console.print(f"[green]✓ {model.name} already downloaded[/green]")
            return

        model_config = DEFAULT_BUILTIN_MODELS[model_id]
        await _download_with_progress(
            manager,
            model_id,
            model_config["modelscope_id"],
            model_config["filename"],
            model.name if model else model_id,
        )
        return

    # 如果不是内置模型，尝试作为 ModelScope 模型 ID 下载
    if model_id and "/" in model_id:
        console.print(f"\n[bold]Fetching files for {model_id}...[/bold]")
        files = await manager.get_modelscope_files(model_id)

        gguf_files = [f for f in files if f.get("Name", "").endswith(".gguf")]

        if not gguf_files:
            console.print("[yellow]No GGUF files found in this model.[/yellow]")
            return

        console.print("\n[bold]Available GGUF files:[/bold]")
        sorted_files = sorted(gguf_files, key=lambda x: x.get("Size", 0))
        for i, f in enumerate(sorted_files, 1):
            size_mb = f.get("Size", 0) / (1024 * 1024)
            console.print(f"  [{i}] {f.get('Name')} ({size_mb:.0f} MB)")

        file_choice = Prompt.ask(
            "\nSelect file to download",
            choices=[str(i) for i in range(1, len(sorted_files) + 1)],
            default="1",
        )

        selected_file = sorted_files[int(file_choice) - 1]
        filename = selected_file.get("Name", "")
        size_mb = selected_file.get("Size", 0) / (1024 * 1024)

        custom_id = f"custom:{model_id.replace('/', '-')}"
        manager.add_custom_model(
            model_id=custom_id,
            name=model_id,
            modelscope_id=model_id,
            filename=filename,
            size_mb=size_mb,
        )

        await _download_with_progress(
            manager,
            custom_id,
            model_id,
            filename,
            model_id,
        )
        return

    # 没有指定模型 ID，下载所有未下载的内置模型
    if not model_id:
        models = [m for m in manager.list_models() if not m.downloaded]
        if not models:
            console.print("[green]All models already downloaded![/green]")
            return

    # 处理内置模型
    if model_id:
        found = manager.get_model(model_id)
        models = [found] if found else []
        if not models[0]:
            console.print(f"[red]Unknown model: {model_id}[/red]")
            console.print("[dim]Available models:[/dim]")
            for m in manager.list_models():
                console.print(f"  {m.model_id} - {m.name}")
            return
    else:
        models = [m for m in manager.list_models() if not m.downloaded]

    for model in models:
        if model.downloaded:
            console.print(f"[green]✓ {model.name} already downloaded[/green]")
            continue

        model_config = DEFAULT_BUILTIN_MODELS.get(model.model_id, {})
        await _download_with_progress(
            manager,
            model.model_id,
            model_config.get("modelscope_id", ""),
            model_config.get("filename", ""),
            model.name,
        )


async def _download_with_progress(
    manager: LocalModelManager,
    model_id: str,
    modelscope_id: str,
    filename: str,
    display_name: str,
) -> None:
    """Download a model with Rich progress bar."""
    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        DownloadColumn(),
        "•",
        TransferSpeedColumn(),
        "•",
        TimeRemainingColumn(),
        console=console,
    )

    with progress:
        task_id = progress.add_task(f"Downloading {display_name}", total=None)

        def progress_callback(pct, downloaded, total):
            if total > 0:
                progress.update(task_id, total=total, completed=downloaded)

        try:
            await manager.download_from_modelscope(modelscope_id, filename, progress_callback)
            progress.update(task_id, completed=progress.tasks[task_id].total or 0)
            console.print("[green]✓ Download complete![/green]")
            if model_id.startswith("custom:"):
                console.print(f"[dim]Model ID: {model_id}[/dim]")
        except Exception as e:
            console.print(f"\n[red]✗ Download failed: {e}[/red]")
            raise


def run_download(model_id: str | None = None) -> None:
    """Run download in async loop."""
    asyncio.run(download_model(model_id))


def list_models() -> None:
    """List all available models (built-in + custom)."""
    manager = LocalModelManager()
    models = manager.list_models()
    usage = manager.get_disk_usage()

    builtin_models = [m for m in models if not m.model_id.startswith("custom:")]
    custom_models = [m for m in models if m.model_id.startswith("custom:")]

    console.print("\n[bold]Built-in Models (ModelScope)[/bold]\n")

    table = Table(show_header=True)
    table.add_column("Model ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Size", style="dim")
    table.add_column("Status", style="green")
    table.add_column("Description", style="dim")

    for model in builtin_models:
        status = (
            "[green]✓ downloaded[/green]" if model.downloaded else "[yellow]not downloaded[/yellow]"
        )
        table.add_row(
            model.model_id,
            model.name,
            f"{model.size_mb} MB",
            status,
            model.description,
        )

    console.print(table)

    if custom_models:
        console.print("\n[bold]Custom Downloaded Models[/bold]\n")

        table = Table(show_header=True)
        table.add_column("Model ID", style="cyan")
        table.add_column("Name", style="bold")
        table.add_column("Size", style="dim")
        table.add_column("Status", style="green")
        table.add_column("Source", style="dim")

        for model in custom_models:
            status = (
                "[green]✓ downloaded[/green]"
                if model.downloaded
                else "[yellow]not downloaded[/yellow]"
            )
            table.add_row(
                model.model_id,
                model.name,
                f"{model.size_mb:.0f} MB",
                status,
                model.modelscope_id,
            )

        console.print(table)

    console.print(
        f"\n[dim]Disk usage: {usage['total_mb']:.1f} MB ({usage['models_downloaded']}/{usage['models_available']} models)[/dim]\n"
    )


def remove_model(model_id: str) -> None:
    """Remove a downloaded model."""
    manager = LocalModelManager()
    model = manager.get_model(model_id)

    if not model:
        console.print(f"[red]Unknown model: {model_id}[/red]")
        return

    if not model.downloaded:
        console.print(f"[yellow]Model not downloaded: {model.name}[/yellow]")
        return

    from rich.prompt import Confirm

    confirm = Confirm.ask(
        f"Remove {model.name} ({model.size_mb} MB)?",
        default=False,
    )

    if confirm:
        if manager.remove_model(model_id):
            console.print(f"[green]✓ Removed {model.name}[/green]")
        else:
            console.print(f"[red]✗ Failed to remove {model.name}[/red]")


def show_model_info(model_id: str) -> None:
    """Show detailed information about a model."""
    manager = LocalModelManager()
    model = manager.get_model(model_id)

    if not model:
        console.print(f"[red]Unknown model: {model_id}[/red]")
        return

    console.print(f"\n[bold]{model.name}[/bold]")
    console.print(f"Model ID: {model.model_id}")
    console.print(f"ModelScope ID: {model.modelscope_id}")
    console.print(f"Size: {model.size_mb} MB")
    console.print(
        f"Status: {'[green]Downloaded[/green]' if model.downloaded else '[yellow]Not downloaded[/yellow]'}"
    )
    console.print(f"Description: {model.description}")
    console.print(f"Tags: {', '.join(model.tags)}")

    if model.downloaded:
        file_size = os.path.getsize(model.path) / (1024 * 1024)
        console.print(f"Path: {model.path}")
        console.print(f"File size: {file_size:.1f} MB")

    console.print()


async def search_modelscope(query: str) -> None:
    """Search for models on ModelScope and allow download."""
    manager = LocalModelManager()

    console.print(f"\n[bold]Searching ModelScope for: {query}[/bold]")
    console.print("[dim]Searching across official and community GGUF publishers...[/dim]\n")

    results = await manager.search_modelscope(query)

    if not results:
        console.print("[yellow]No GGUF models found.[/yellow]")
        console.print(
            "[dim]Try different search terms like 'qwen3', 'qwen2.5', 'llama', 'gemma', 'phi', etc.[/dim]"
        )
        return

    table = Table(show_header=True)
    table.add_column("#", style="cyan")
    table.add_column("Model ID", style="bold")
    table.add_column("Downloads", style="dim")
    table.add_column("GGUF Files", style="dim")
    table.add_column("Min Size", style="dim")

    for i, model in enumerate(results[:20], 1):
        model_id = model.get("ModelId", "")
        downloads = model.get("Downloads", 0)
        gguf_count = len(model.get("GGUFFiles", []))
        min_size = model.get("SmallestSizeMB", 0)

        table.add_row(
            str(i),
            model_id,
            str(downloads),
            str(gguf_count),
            f"{min_size:.0f} MB",
        )

    console.print(table)
    console.print()

    choice = Prompt.ask(
        "Enter number to download (or 'q' to quit)",
        default="q",
    )

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(results):
            selected = results[idx]
            model_id = selected.get("ModelId", "")
            gguf_files = selected.get("GGUFFiles", [])

            console.print(f"\n[bold]Available GGUF files for {model_id}:[/bold]")
            # 按大小排序显示
            sorted_files = sorted(gguf_files, key=lambda x: x.get("Size", 0))
            for i, f in enumerate(sorted_files, 1):
                size_mb = f.get("Size", 0) / (1024 * 1024)
                console.print(f"  [{i}] {f.get('Name')} ({size_mb:.0f} MB)")

            file_choice = Prompt.ask(
                "\nSelect file to download",
                choices=[str(i) for i in range(1, len(sorted_files) + 1)],
                default="1",
            )

            selected_file = sorted_files[int(file_choice) - 1]
            filename = selected_file.get("Name", "")
            size_mb = selected_file.get("Size", 0) / (1024 * 1024)

            custom_id = f"custom:{model_id.replace('/', '-')}"
            manager.add_custom_model(
                model_id=custom_id,
                name=model_id,
                modelscope_id=model_id,
                filename=filename,
                size_mb=size_mb,
                description=selected.get("Description", ""),
            )

            def progress(pct, downloaded, total):
                bars = int(pct / 5)
                bar_str = "█" * bars + "░" * (20 - bars)
                console.print(
                    f"\r  [{bar_str}] {pct:.0f}% ({downloaded / 1024 / 1024:.1f} MB)",
                    end="",
                )

            try:
                await _download_with_progress(
                    manager,
                    custom_id,
                    model_id,
                    filename,
                    model_id,
                )
            except Exception as e:
                console.print(f"\n[red]✗ Download failed: {e}[/red]")


def run_search(query: str) -> None:
    """Run search in async loop."""
    asyncio.run(search_modelscope(query))
