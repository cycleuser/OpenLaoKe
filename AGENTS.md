# AGENTS.md - OpenLaoKe

OpenLaoKe is an open-source terminal AI coding assistant (Python 3.11+ CLI), similar to Claude Code or Cursor.

## Commands

### Setup
```bash
uv pip install -e ".[dev]"   # Install with dev dependencies (recommended)
pip install -e ".[dev]"      # Alternative with pip
```

### Lint & Format
```bash
ruff check .                 # Lint (fix: ruff check . --fix)
ruff format .                # Format (fix: ruff format .)
```

### Type Check
```bash
mypy                         # Run mypy (not strict mode)
```

### Test
```bash
pytest                       # Full test suite
pytest --cov                 # With coverage
pytest tests/test_tools.py   # Single file
pytest tests/test_tools.py::TestBashTool::test_simple_command  # Single test
pytest -v                    # Verbose output
pytest -x                    # Stop on first failure
pytest -k "keyword"          # Filter by name
```

## Code Style

### Imports
- `from __future__ import annotations` at top of every module
- Order: stdlib → third-party → local (enforced by ruff `I`)
- Use `TYPE_CHECKING` guard for circular imports
- Absolute imports from `openlaoke.` prefix (no relative imports)

### Types
- Full type annotations on all function signatures (params + return)
- Use `|` for unions (e.g., `str | None`, not `Optional[str]`)
- Use `dataclass` for data structures
- Use `pydantic BaseModel` for tool input schemas
- Use `Enum` for constants (e.g., `PermissionMode`, `TaskStatus`)

### Naming
- Classes: `PascalCase` (`AppState`, `ToolRegistry`)
- Functions/methods: `snake_case` (`create_app_state`, `check_tool`)
- Constants: `UPPER_SNAKE_CASE` (`PREFIXES`, `MAX_TOKENS`)
- Private attributes: leading underscore (`_listeners`, `_persist_path`)

### Formatting
- Line length: 100 characters (E501 ignored, so soft limit)
- Ruff rules: E, F, I, N, W, UP, B, SIM
- mypy: not strict, but warns on `return Any` and unused ignores

### Error Handling
- Tool methods return `ToolResultBlock` with `is_error=True` rather than raising
- Use `try/except Exception` with silent pass for non-critical operations
- Validation returns `ValidationResult(result=False, message=..., error_code=...)`
- Log errors, don't crash the REPL

### Async Patterns
- Tool `call()` methods are `async def`
- Tests use `pytest-asyncio` in "auto" mode
- Use `asyncio` for async operations throughout

### Docstrings
- Module-level docstrings on every file
- Class-level docstrings for key classes
- Method docstrings for abstract/important methods

## Architecture

```
openlaoke/
├── core/           # State, tools, tasks, REPL, config, skills
├── tools/          # Built-in tool implementations (Bash, Read, Write, etc.)
├── commands/       # Slash commands and registry
├── types/          # Type definitions (core_types, permissions, providers)
├── services/       # External services (MCP)
├── components/     # UI components (rich-based TUI)
├── utils/          # Utilities (config, compute)
├── entrypoints/    # CLI entry point
└── hooks/          # Hook implementations
tests/              # Test suite (5 modules)
```

## Key Patterns
- **State**: Centralized `AppState` (dataclass, observer pattern, persistence)
- **Tools**: Abstract `Tool` base class with `call()` → `ToolResultBlock`
- **Commands**: Slash commands via `Command` base class + registry
- **Providers**: Multi-provider API client (Anthropic, OpenAI, MiniMax, Aliyun, Ollama)
- **Skills**: YAML-based skill system with dynamic loading
