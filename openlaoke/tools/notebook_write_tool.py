"""NotebookWrite tool - write Jupyter notebooks."""

from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class NotebookWriteInput(BaseModel):
    file_path: str = Field(description="Path to the notebook file")
    source: str = Field(description="Python source code for the cell")
    cell_type: str = Field(default="code", description="Cell type: 'code' or 'markdown'")
    cell_index: int = Field(default=-1, description="Index to insert the cell at (-1 for append)")


class NotebookWriteTool(Tool):
    """Write cells to Jupyter notebooks."""

    name = "NotebookWrite"
    description = (
        "Write a cell to a Jupyter notebook (.ipynb). "
        "Creates the notebook if it doesn't exist. Supports code and markdown cells."
    )
    input_schema = NotebookWriteInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        file_path = kwargs.get("file_path", "")
        source = kwargs.get("source", "")
        cell_type = kwargs.get("cell_type", "code")
        cell_index = kwargs.get("cell_index", -1)

        if not file_path:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: file_path is required",
                is_error=True,
            )

        abs_path = self._resolve_path(file_path, ctx.app_state.get_cwd())

        try:
            if os.path.exists(abs_path):
                with open(abs_path, encoding="utf-8") as f:
                    nb = json.load(f)
            else:
                nb = {
                    "cells": [],
                    "metadata": {
                        "kernelspec": {
                            "display_name": "Python 3",
                            "language": "python",
                            "name": "python3",
                        }
                    },
                    "nbformat": 4,
                    "nbformat_minor": 5,
                }

            cell = {
                "cell_type": cell_type,
                "source": source.split("\n"),
                "metadata": {},
            }
            if cell_type == "code":
                cell["outputs"] = []
                cell["execution_count"] = None

            if cell_index >= 0:
                nb["cells"].insert(cell_index, cell)
            else:
                nb["cells"].append(cell)

            with open(abs_path, "w", encoding="utf-8") as f:
                json.dump(nb, f, indent=1)

            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Added {cell_type} cell to {abs_path} (total cells: {len(nb['cells'])})",
                is_error=False,
            )

        except json.JSONDecodeError:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: {abs_path} is not a valid notebook file",
                is_error=True,
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error writing notebook: {e}",
                is_error=True,
            )

    def _resolve_path(self, path: str, cwd: str) -> str:
        if os.path.isabs(path):
            return os.path.normpath(path)
        return os.path.normpath(os.path.join(cwd, path))


def register(registry: ToolRegistry) -> None:
    registry.register(NotebookWriteTool())
