# OpenLaoKe

Open-source terminal AI coding assistant.

## Features

- **Interactive REPL** with rich terminal UI
- **Multi-Provider Support** - Anthropic, OpenAI, Ollama, LM Studio, and custom endpoints
- **Tool System** with 9 built-in tools:
  - `Bash` - Execute shell commands with streaming output
  - `Read` - Read file contents with line range support
  - `Write` - Create/overwrite files
  - `Edit` - Targeted find-and-replace file edits with diff output
  - `Glob` - Fast file pattern matching (respects .gitignore)
  - `Grep` - Regex search across files with multiple output modes
  - `Agent` - Spawn sub-agents for parallel work
  - `Taskkill` - Kill running tasks
  - `NotebookWrite` - Write Jupyter notebook cells
- **MCP Support** - Connect to external MCP tool servers
- **Permission System** - Three modes: default, auto, bypass
- **Session Persistence** - Auto-save and resume sessions
- **Cost Tracking** - Real-time token usage and cost display
- **Slash Commands** - 11 built-in commands (`/help`, `/model`, `/cost`, `/compact`, etc.)
- **Hook System** - Extensible pre/post hooks for tool and API calls
- **Proxy Support** - No proxy, system proxy, or custom proxy

## Installation

```bash
# Clone and install
cd OpenLaoKe
pip install -e .

# Or with uv (recommended)
uv pip install -e .
```

## Usage

```bash
# First run (shows configuration wizard)
openlaoke

# Reconfigure
openlaoke --config

# Non-interactive mode
openlaoke "Write a Python script that sorts a list"

# With options
openlaoke -m gpt-4o -p auto
openlaoke --provider ollama -m llama3.2
openlaoke --proxy http://127.0.0.1:7890
openlaoke --cwd /path/to/project
```

## Supported Providers

| Provider | Type | API Key Required |
|----------|------|------------------|
| Anthropic | Cloud | Yes |
| OpenAI | Cloud | Yes |
| Ollama | Local | No |
| LM Studio | Local | No |
| OpenAI-Compatible | Custom | Optional |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENLAOKE_MODEL` | Default model |

## Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/exit` | Exit OpenLaoKe |
| `/clear` | Clear screen and conversation |
| `/model [name]` | Show or change model |
| `/permission [mode]` | Change permission mode |
| `/compact` | Compact conversation |
| `/cost` | Show session cost and usage |
| `/cwd [path]` | Show or change working directory |
| `/resume` | Resume last session |
| `/commands` | Show example commands |
| `/settings` | Show current settings |

## Architecture

```
openlaoke/
├── core/           # Core systems
│   ├── state.py    # Centralized state management
│   ├── tool.py     # Tool base class and registry
│   ├── task.py     # Task lifecycle management
│   ├── multi_provider_api.py  # Multi-provider API client
│   ├── repl.py     # REPL interaction loop
│   ├── config_wizard.py  # Configuration wizard
│   └── ...
├── tools/          # Tool implementations
├── commands/       # Slash commands
├── services/       # External services (MCP)
├── components/     # UI components (TUI)
├── types/          # Type definitions
└── utils/          # Utilities
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run linter
ruff check .

# Run tests
pytest

# Build package
python -m build
```

## Configuration

User config is stored at `~/.openlaoke/config.json`. You can edit it directly or use `/settings` in the REPL.

## License

GPLv3