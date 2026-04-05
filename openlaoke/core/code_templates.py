"""Code templates and project scaffolds for quick development.

Provides ready-to-use templates for common development scenarios
across multiple programming languages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ProjectType(StrEnum):
    CLI_TOOL = "cli_tool"
    WEB_API = "web_api"
    WEB_APP = "web_app"
    GUI_APP = "gui_app"
    LIBRARY = "library"
    DATA_PROCESSING = "data_processing"
    TESTING = "testing"
    DATABASE = "database"
    MICROSERVICE = "microservice"
    SCRIPT = "script"


class Language(StrEnum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    CPP = "cpp"


@dataclass
class CodeTemplate:
    name: str
    description: str
    language: Language
    project_type: ProjectType
    files: dict[str, str]
    dependencies: list[str] = field(default_factory=list)
    setup_commands: list[str] = field(default_factory=list)
    readme: str = ""


PROJECT_TEMPLATES: dict[str, CodeTemplate] = {
    "python_cli_tool": CodeTemplate(
        name="Python CLI Tool",
        description="Command-line tool with argument parsing, logging, and config",
        language=Language.PYTHON,
        project_type=ProjectType.CLI_TOOL,
        dependencies=["click>=8.0", "rich>=13.0"],
        setup_commands=["pip install click rich"],
        files={
            "main.py": '''"""Main entry point for CLI tool."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import click
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)


@click.command()
@click.option("--input", "-i", required=True, help="Input file path")
@click.option("--output", "-o", default="output.txt", help="Output file path")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.version_option(version="1.0.0")
def main(input: str, output: str, verbose: bool) -> None:
    """Process input file and generate output."""
    setup_logging(verbose)
    
    input_path = Path(input)
    if not input_path.exists():
        console.print(f"[red]Error: Input file not found: {input}[/red]")
        raise SystemExit(1)
    
    console.print(f"[green]Processing: {input_path}[/green]")
    
    result = process_file(input_path)
    
    output_path = Path(output)
    output_path.write_text(result)
    
    console.print(f"[green]Output saved to: {output_path}[/green]")


def setup_logging(verbose: bool) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def process_file(input_path: Path) -> str:
    """Process input file and return result."""
    content = input_path.read_text()
    logger.info(f"Read {len(content)} characters from {input_path}")
    
    result = content.upper()
    
    return result


if __name__ == "__main__":
    main()
''',
            "config.py": '''"""Configuration management."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import json


@dataclass
class Config:
    """Application configuration."""
    input_dir: Path = Path(".")
    output_dir: Path = Path("output")
    max_workers: int = 4
    timeout: int = 30
    
    @classmethod
    def from_file(cls, config_path: Path) -> Config:
        """Load configuration from JSON file."""
        if not config_path.exists():
            return cls()
        
        with open(config_path) as f:
            data = json.load(f)
        
        return cls(
            input_dir=Path(data.get("input_dir", ".")),
            output_dir=Path(data.get("output_dir", "output")),
            max_workers=data.get("max_workers", 4),
            timeout=data.get("timeout", 30),
        )
    
    def to_file(self, config_path: Path) -> None:
        """Save configuration to JSON file."""
        data = {
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "max_workers": self.max_workers,
            "timeout": self.timeout,
        }
        
        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)
''',
            "utils.py": '''"""Utility functions."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any


def calculate_file_hash(file_path: Path) -> str:
    """Calculate MD5 hash of a file."""
    md5_hash = hashlib.md5()
    
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)
    
    return md5_hash.hexdigest()


def timing_decorator(func: Any) -> Any:
    """Decorator to measure function execution time."""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} took {end - start:.2f} seconds")
        return result
    return wrapper
''',
            "pyproject.toml": """[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-tool"
version = "1.0.0"
description = "CLI tool for file processing"
requires-python = ">=3.10"
dependencies = [
    "click>=8.0",
    "rich>=13.0",
]

[project.scripts]
cli-tool = "main:main"

[tool.ruff]
line-length = 100
target-version = "py310"
""",
        },
        readme="""# CLI Tool

A command-line tool for file processing.

## Installation

```bash
pip install -e .
```

## Usage

```bash
cli-tool --input file.txt --output result.txt
cli-tool -i file.txt -o result.txt -v
```

## Features

- Argument parsing with Click
- Rich console output
- Logging support
- Configuration management
- Utility functions
""",
    ),
    "python_web_api": CodeTemplate(
        name="Python Web API",
        description="RESTful API with FastAPI, models, and error handling",
        language=Language.PYTHON,
        project_type=ProjectType.WEB_API,
        dependencies=["fastapi>=0.100", "uvicorn>=0.23", "pydantic>=2.0"],
        setup_commands=["pip install fastapi uvicorn pydantic"],
        files={
            "main.py": '''"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from models import Item, ItemCreate, ItemUpdate
from database import Database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    app.state.db = Database()
    yield
    app.state.db.close()


app = FastAPI(
    title="API Server",
    description="RESTful API with FastAPI",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "API is running"}


@app.get("/items", response_model=list[Item])
async def list_items(skip: int = 0, limit: int = 100) -> list[Item]:
    """List all items."""
    return app.state.db.get_items(skip=skip, limit=limit)


@app.get("/items/{item_id}", response_model=Item)
async def get_item(item_id: int) -> Item:
    """Get item by ID."""
    item = app.state.db.get_item(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found"
        )
    return item


@app.post("/items", response_model=Item, status_code=status.HTTP_201_CREATED)
async def create_item(item: ItemCreate) -> Item:
    """Create a new item."""
    return app.state.db.create_item(item)


@app.put("/items/{item_id}", response_model=Item)
async def update_item(item_id: int, item: ItemUpdate) -> Item:
    """Update an item."""
    updated = app.state.db.update_item(item_id, item)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found"
        )
    return updated


@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int) -> None:
    """Delete an item."""
    if not app.state.db.delete_item(item_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
''',
            "models.py": '''"""Pydantic models for API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ItemBase(BaseModel):
    """Base item model."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    price: float = Field(..., gt=0)
    is_active: bool = True


class ItemCreate(ItemBase):
    """Model for creating items."""
    pass


class ItemUpdate(BaseModel):
    """Model for updating items."""
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    price: float | None = Field(None, gt=0)
    is_active: bool | None = None


class Item(ItemBase):
    """Complete item model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: datetime
''',
            "database.py": '''"""In-memory database implementation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from models import Item, ItemCreate, ItemUpdate


class Database:
    """In-memory database."""
    
    def __init__(self) -> None:
        self._items: dict[int, Item] = {}
        self._next_id = 1
    
    def get_items(self, skip: int = 0, limit: int = 100) -> list[Item]:
        """Get all items with pagination."""
        items = list(self._items.values())
        return items[skip:skip + limit]
    
    def get_item(self, item_id: int) -> Item | None:
        """Get item by ID."""
        return self._items.get(item_id)
    
    def create_item(self, item: ItemCreate) -> Item:
        """Create a new item."""
        now = datetime.now()
        new_item = Item(
            id=self._next_id,
            name=item.name,
            description=item.description,
            price=item.price,
            is_active=item.is_active,
            created_at=now,
            updated_at=now,
        )
        self._items[self._next_id] = new_item
        self._next_id += 1
        return new_item
    
    def update_item(self, item_id: int, item: ItemUpdate) -> Item | None:
        """Update an item."""
        if item_id not in self._items:
            return None
        
        existing = self._items[item_id]
        update_data = item.model_dump(exclude_unset=True)
        
        updated_item = Item(
            id=existing.id,
            name=update_data.get("name", existing.name),
            description=update_data.get("description", existing.description),
            price=update_data.get("price", existing.price),
            is_active=update_data.get("is_active", existing.is_active),
            created_at=existing.created_at,
            updated_at=datetime.now(),
        )
        
        self._items[item_id] = updated_item
        return updated_item
    
    def delete_item(self, item_id: int) -> bool:
        """Delete an item."""
        if item_id not in self._items:
            return False
        del self._items[item_id]
        return True
    
    def close(self) -> None:
        """Close database connection."""
        self._items.clear()
''',
        },
        readme="""# Web API

FastAPI-based RESTful API server.

## Installation

```bash
pip install -r requirements.txt
```

## Running

```bash
uvicorn main:app --reload
```

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Endpoints

- GET / - Root endpoint
- GET /items - List items
- GET /items/{id} - Get item
- POST /items - Create item
- PUT /items/{id} - Update item
- DELETE /items/{id} - Delete item
""",
    ),
    "python_data_processing": CodeTemplate(
        name="Python Data Processing",
        description="Data processing pipeline with pandas, multiprocessing, and validation",
        language=Language.PYTHON,
        project_type=ProjectType.DATA_PROCESSING,
        dependencies=["pandas>=2.0", "numpy>=1.24", "pydantic>=2.0"],
        setup_commands=["pip install pandas numpy pydantic"],
        files={
            "processor.py": '''"""Data processing pipeline."""

from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, validator

logger = logging.getLogger(__name__)


class DataConfig(BaseModel):
    """Configuration for data processing."""
    input_file: Path
    output_file: Path
    chunk_size: int = 10000
    max_workers: int = 4
    
    @validator("input_file")
    def input_must_exist(cls, v: Path) -> Path:
        if not v.exists():
            raise ValueError(f"Input file not found: {v}")
        return v


class DataProcessor:
    """Process large datasets in parallel."""
    
    def __init__(self, config: DataConfig) -> None:
        self.config = config
        self.stats: dict[str, Any] = {}
    
    def process(self) -> pd.DataFrame:
        """Process data in chunks."""
        logger.info(f"Processing {self.config.input_file}")
        
        chunks = []
        for chunk in pd.read_csv(
            self.config.input_file,
            chunksize=self.config.chunk_size
        ):
            processed = self._process_chunk(chunk)
            chunks.append(processed)
        
        result = pd.concat(chunks, ignore_index=True)
        
        result.to_csv(self.config.output_file, index=False)
        logger.info(f"Saved to {self.config.output_file}")
        
        return result
    
    def _process_chunk(self, chunk: pd.DataFrame) -> pd.DataFrame:
        """Process a single chunk."""
        chunk = chunk.dropna()
        
        numeric_cols = chunk.select_dtypes(include=[np.number]).columns
        chunk[numeric_cols] = chunk[numeric_cols].fillna(0)
        
        return chunk
    
    def process_parallel(self) -> pd.DataFrame:
        """Process data in parallel using multiprocessing."""
        logger.info(f"Parallel processing with {self.config.max_workers} workers")
        
        chunks = list(pd.read_csv(
            self.config.input_file,
            chunksize=self.config.chunk_size
        ))
        
        results = []
        with ProcessPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {
                executor.submit(self._process_chunk, chunk): i
                for i, chunk in enumerate(chunks)
            }
            
            for future in as_completed(futures):
                chunk_id = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(f"Processed chunk {chunk_id}")
                except Exception as e:
                    logger.error(f"Error in chunk {chunk_id}: {e}")
        
        final = pd.concat(results, ignore_index=True)
        final.to_csv(self.config.output_file, index=False)
        
        return final
    
    def get_statistics(self, df: pd.DataFrame) -> dict[str, Any]:
        """Calculate data statistics."""
        return {
            "rows": len(df),
            "columns": len(df.columns),
            "memory_mb": df.memory_usage(deep=True).sum() / 1024 / 1024,
            "null_counts": df.isnull().sum().to_dict(),
            "dtypes": df.dtypes.astype(str).to_dict(),
        }


def main() -> None:
    """Main entry point."""
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    config = DataConfig(
        input_file=Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data.csv"),
        output_file=Path("output.csv"),
        chunk_size=10000,
        max_workers=4,
    )
    
    processor = DataProcessor(config)
    result = processor.process_parallel()
    
    stats = processor.get_statistics(result)
    print(f"Processed {stats['rows']} rows, {stats['columns']} columns")
    print(f"Memory: {stats['memory_mb']:.2f} MB")


if __name__ == "__main__":
    main()
''',
            "validators.py": '''"""Data validation utilities."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, validator


class DataValidator(BaseModel):
    """Validate data rows."""
    
    id: int
    name: str
    value: float
    category: str
    
    @validator("id")
    def id_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("ID must be positive")
        return v
    
    @validator("name")
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()
    
    @validator("value")
    def value_in_range(cls, v: float) -> float:
        if not 0 <= v <= 1000:
            raise ValueError("Value must be between 0 and 1000")
        return v
    
    @validator("category")
    def category_valid(cls, v: str) -> str:
        valid = ["A", "B", "C", "D"]
        if v not in valid:
            raise ValueError(f"Category must be one of {valid}")
        return v


def validate_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Validate a DataFrame."""
    errors = []
    valid_rows = []
    
    for idx, row in df.iterrows():
        try:
            validated = DataValidator(**row.to_dict())
            valid_rows.append(validated.dict())
        except Exception as e:
            errors.append(f"Row {idx}: {e}")
    
    return pd.DataFrame(valid_rows), errors
''',
        },
        readme="""# Data Processing

High-performance data processing pipeline.

## Features

- Chunk-based processing for large files
- Parallel processing with multiprocessing
- Data validation with Pydantic
- Statistics calculation
- Memory-efficient operations

## Usage

```bash
python processor.py input.csv
```

## Processing Steps

1. Read data in chunks
2. Clean and validate
3. Process in parallel
4. Aggregate results
5. Save to output
""",
    ),
}


def get_template(template_id: str) -> CodeTemplate | None:
    """Get a template by ID."""
    return PROJECT_TEMPLATES.get(template_id)


def get_templates_for_project_type(project_type: ProjectType) -> list[CodeTemplate]:
    """Get all templates for a project type."""
    return [
        template for template in PROJECT_TEMPLATES.values() if template.project_type == project_type
    ]


def get_templates_for_language(language: Language) -> list[CodeTemplate]:
    """Get all templates for a language."""
    return [template for template in PROJECT_TEMPLATES.values() if template.language == language]


def list_available_templates() -> dict[str, str]:
    """List all available templates."""
    return {
        template_id: template.description for template_id, template in PROJECT_TEMPLATES.items()
    }


def suggest_template(task_description: str) -> list[str]:
    """Suggest appropriate templates based on task description."""
    task_lower = task_description.lower()

    suggestions = []

    if any(word in task_lower for word in ["cli", "command", "argument", "terminal"]):
        suggestions.append("python_cli_tool")

    if any(word in task_lower for word in ["api", "web", "rest", "endpoint", "server"]):
        suggestions.append("python_web_api")

    if any(word in task_lower for word in ["data", "process", "csv", "pandas", "analysis"]):
        suggestions.append("python_data_processing")

    if not suggestions:
        suggestions.append("python_cli_tool")

    return suggestions
