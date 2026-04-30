# OpenLaoKe

> Open-source terminal AI coding assistant with advanced automation, local model support, and intelligent supervision.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: GPLv3](https://img.shields.io/badge/license-GPLv3-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

## Overview

OpenLaoKe is a powerful terminal-based AI coding assistant that supports **24+ AI providers**, **local GGUF models** (zero API cost), and **advanced automation** features. Whether you need cloud-powered intelligence or completely offline AI coding, OpenLaoKe has you covered.

## Key Features

### Core Capabilities
- **Interactive REPL** with rich terminal UI, command history (↑/↓, Ctrl+R), and smart autocomplete (Tab)
- **Multi-Provider Support** — 24 AI providers including cloud, local, and free options
- **Local GGUF Models** — Run Qwen models locally with zero API cost, zero network needed
- **Ctrl+P Model Picker** — VS Code-style model switching overlay for instant provider/model changes
- **30+ Built-in Tools** — Read, Write, Edit, Glob, Grep, Bash, LSP, Git, WebSearch, and more
- **MCP Support** — Connect to external Model Context Protocol tool servers
- **Permission System** — Three modes: default, auto, bypass
- **Session Persistence** — Auto-save and resume conversations
- **Cost Tracking** — Real-time token usage and cost display
- **20+ Slash Commands** — Model switching, configuration, debugging, and more
- **Hook System** — Extensible pre/post execution hooks
- **Proxy Support** — No proxy, system proxy, or custom proxy

### Advanced Features
- **HyperAuto Mode** — Fully autonomous operation with self-improvement and skill generation
- **Task Supervision** — Automatic retry, completion verification, and quality checking
- **Model Assessment** — 5-tier adaptive task decomposition based on model capabilities
- **Anti-AI Detection** — Ensures generated content appears human-written with real citations
- **Distilled Prompt Templates** — 79 pre-populated Q&A templates across 31 categories with multi-language triggers (CN/EN/JP/KR/FR/DE/ES/RU)
- **Reference Download** — Automatic PDF download for academic writing
- **Skill System** — 39+ YAML-based skills for specialized workflows
- **Small Model Optimizations** — Tool argument type coercion, JSON schema sanitization, read-loop prevention, terminal output compression, and model-size-adaptive behavior for GGUF models (0.6B-8B)
- **Fast Context Pruning** — Pure-algorithm context compression (<5ms, no LLM call) with head-tail preservation and keyword extraction
- **Hook System** — 15 extension points for pre/post tool execution, message transformation, error handling, and more
- **Self-Reflection Tracker** — Empirical strategy tracking that auto-disables failing approaches and recommends better alternatives based on real outcomes

## Quick Start

```bash
# Install with pip
pip install openlaoke

# Install from source (development)
pip install -e .

# Or with uv (recommended for development)
uv pip install -e ".[dev]"

# With local GGUF model support
pip install -e ".[local]"

# Start OpenLaoKe
openlaoke
```

## Supported Providers

### Free Models (No API Key Required)
| Provider | Models | Notes |
|----------|--------|-------|
| **OpenCode Zen** | `big-pickle`, `gpt-5-nano` | Completely free, no registration |
| **Built-in GGUF** | `qwen3:0.6b`, `qwen2.5:0.5b/1.5b/3b` | Local CPU inference, zero cost |

### Cloud Providers
| Provider | Models | API Key |
|----------|--------|---------|
| Anthropic | Claude 4 Sonnet/Opus, Claude 3.5 | Yes |
| OpenAI | GPT-4o, GPT-4o-mini, o1-preview | Yes |
| MiniMax | MiniMax-M2.7, M2.5, M2.1 | Yes |
| Aliyun Coding Plan | Qwen3.5-plus, Kimi-k2.5, GLM-5 | Yes |
| Azure OpenAI | GPT-4o, GPT-4o-mini, GPT-35-turbo | Yes |
| Google AI | Gemini 2.0 Flash/Pro, 1.5 Flash/Pro | Yes |
| Google Vertex AI | Gemini via GCP | Yes |
| AWS Bedrock | Claude 3.5, Llama 3.1, Amazon Nova | Yes |
| xAI Grok | Grok-2-latest, Grok-beta | Yes |
| Mistral AI | Mistral-large, Mistral-small, Codestral | Yes |
| Groq | Llama 3.3 70B, Llama 3.1 8B | Yes |
| Cerebras | Llama 3.3 70B, Llama 3.1 8B/70B | Yes |
| Cohere | Command-r-plus, Command-r | Yes |
| DeepInfra | Llama 3.3/3.1, Mistral-small | Yes |
| Together AI | Llama 3.3/3.1, Mistral, Qwen 2.5 | Yes |
| Perplexity | Sonar models | Yes |
| OpenRouter | Multi-provider access | Yes |
| GitHub Copilot | GPT-4o, GPT-4o-mini, o1 | Yes |

### Local Providers
| Provider | Models | Setup |
|----------|--------|-------|
| Ollama | Gemma 3/4, Llama 3.1/3.2, CodeLlama | Install Ollama |
| LM Studio | Any local model | Install LM Studio |
| **Built-in GGUF** | Qwen models, any ModelScope GGUF | Optional `pip install llama-cpp-python` |
| OpenAI-Compatible | Any OpenAI-compatible endpoint | Custom URL |

## Local GGUF Models (Zero API Cost)

Run AI models completely locally with no API key or network connection. Powered by [llama-cpp-python](https://github.com/abetlen/llama-cpp-python).

### Installation
```bash
pip install openlaoke
```

> Local GGUF model support requires `llama-cpp-python`. If not installed, the config wizard will prompt to install it when you select built-in models. On Linux, you may need `sudo apt install build-essential cmake` first.

### Built-in Models
| Model | Size | Min RAM | Description |
|-------|------|---------|-------------|
| Qwen3 0.6B | 610 MB | 1 GB | Alibaba's Qwen3, excellent Chinese/English |
| Qwen2.5 0.5B | 469 MB | 512 MB | Ultra-small, minimal resource usage |
| Qwen2.5 1.5B | 1 GB | 2 GB | Good balance of speed and quality |
| Qwen2.5 3B | 1.9 GB | 4 GB | Better reasoning and coding ability |

### Download Models
```bash
# Download built-in model
openlaoke model download qwen3:0.6b

# Search ModelScope for any GGUF model
openlaoke model search qwen3.5

# Download custom model from ModelScope
openlaoke model download "unsloth/Qwen3.5-0.8B-GGUF"

# List all models with status
openlaoke model list

# Remove a downloaded model
openlaoke model remove custom:unsloth-Qwen3.5-0.8B-GGUF
```

### Configuration
1. Run `openlaoke --config` and select option **3** (Built-in GGUF Model)
2. Choose a model from the list (built-in or custom downloaded)
3. Download directly from the wizard if needed

### Local Model Parameters
Configure via `/localconfig` in REPL or `~/.openlaoke/config.json`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_ctx` | 262144 | Context window size (model max) |
| `temperature` | 0.3 | Sampling temperature (lower = more deterministic) |
| `repetition_penalty` | 1.1 | Repetition penalty (reduces loops) |

```bash
# In REPL
/localconfig n_ctx 32768
/localconfig temperature 0.5
/localconfig repetition_penalty 1.2
```

### Local Model Features
- **Custom model registry persistence** — Models persist across restarts via `~/.openlaoke/models/custom_models.json`
- **Distilled prompt templates** — 79 Q&A templates auto-injected as few-shot context for common tasks
- **Automatic quantization replacement** — New downloads from same repo replace old quantizations
- **Compact system prompt** — ~30 tokens for small models vs ~800 for full prompt
- **`
</think>

` thinking content** — Qwen3.5 thinking process parsed and displayed
- **Context-aware truncation** — Auto-truncates messages to fit context window
- **Ctrl+P model picker** — Switch models instantly from REPL

## Tool System (30+ Tools)

### File Operations
| Tool | Description |
|------|-------------|
| **Read** | Read file contents with line range support |
| **Write** | Create/overwrite files |
| **Edit** | Targeted find-and-replace with diff output |
| **Glob** | Fast file pattern matching (respects .gitignore) |
| **Grep** | Regex search across files |
| **LS** | List directory contents |

### Code Intelligence
| Tool | Description |
|------|-------------|
| **LSP** | Language Server Protocol integration |
| **Git** | Git operations (status, diff, log, blame) |
| **Bash** | Execute shell commands with streaming output |

### Web & Search
| Tool | Description |
|------|-------------|
| **WebSearch** | Search the web for information |
| **WebFetch** | Fetch web page content |
| **SearchAndDownloadPapers** | Search academic papers |

### Task Management
| Tool | Description |
|------|-------------|
| **TodoWrite** | Manage task lists |
| **Taskkill** | Kill running tasks |
| **Batch** | Execute multiple tools in parallel |
| **Agent** | Spawn sub-agents for parallel work |

### Other Tools
Notebook support (Read/Write), Cron scheduling, Memory storage, Hook configuration, Reference management (Download/Batch/Manager).

## Slash Commands

### Model & Provider Management
| Command | Description |
|---------|-------------|
| `/model` | Show current model and available models |
| `/model <name>` | Switch to specific model |
| `/model <1-N>` | Select model by index |
| `/model <provider>/<model>` | Switch provider and model |
| `/model -l` | List all models from all providers |
| `/model -p` | List all providers |
| `/provider` | Show current provider |
| `/provider <name>` | Switch to different provider |
| `/localconfig` | Configure local builtin model params |
| **Ctrl+P** | **Model picker overlay** |

### Local Model Management (CLI)
| Command | Description |
|---------|-------------|
| `openlaoke model download [id]` | Download built-in or ModelScope GGUF model |
| `openlaoke model list` | List all available models with status |
| `openlaoke model search <query>` | Search ModelScope for GGUF models |
| `openlaoke model remove <id>` | Remove a downloaded model |
| `openlaoke model info <id>` | Show model details |

### Session & Configuration
| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/exit` | Exit OpenLaoKe |
| `/clear` | Clear screen and conversation |
| `/resume` | Resume last session |
| `/compact` | Compact conversation to save context |
| `/permission [mode]` | Change permission mode |
| `/settings` | Show current settings |
| `/theme [name]` | Change color theme |
| `/cwd [path]` | Show or change working directory |

### Information & Advanced
| Command | Description |
|---------|-------------|
| `/cost` | Show session cost and token usage |
| `/usage` | Show detailed usage statistics |
| `/commands` | Show example commands |
| `/doctor` | Diagnose configuration issues |
| `/hooks` | Manage hooks |
| `/mcp` | Manage MCP servers |
| `/hyperauto` | Start HyperAuto mode |
| `/skill <name>` | Execute a skill |
| `/memory` | Manage persistent memory |
| `/agents` | Manage sub-agents |
| `/lessons` | View cross-project lessons and strategy statistics |

## Distilled Prompt Templates

79 pre-populated Q&A templates across 31 categories with **multi-language triggers** (CN/EN/JP/KR/FR/DE/ES/RU). Automatically injected as few-shot context when matching user input.

### Categories
| Category | Templates | Coverage |
|----------|-----------|----------|
| **System Commands** | 9 | OS info, processes, network, disk, users, services, logs, security, packages |
| **Shell Scripting** | 10 | Basics, conditionals, loops, functions, text processing, error handling, I/O, arrays, strings, math |
| **Tool Calling** | 5 | When to use Bash, Read, Write, Edit, Glob/Grep |
| **Algorithms** | 10 | Sort, search, trees, graphs, DP, linked lists, stacks, hash, recursion, greedy |
| **File Operations** | 6 | Read, write, CSV, paths, JSON, YAML |
| **Database** | 4 | SQL, SQLite, ORM, Redis |
| **Network** | 3 | HTTP requests, web scraping, WebSocket |
| **Python Advanced** | 3 | Decorators, async/await, context managers |
| **Other** | 29 | Git, testing, debugging, OOP, DevOps, CLI, Web, math, code review, ML, and more |

### How It Works
```
User: "用Python写一个快速排序"
→ Matches "code_sort" template (trigger: "排序")
→ Injects quicksort example into system prompt
→ Small model generates better code with reference
```

## Skill System (39+ Skills)

YAML-based skills for specialized workflows:

| Skill | Description |
|-------|-------------|
| `/academic-writer` | Academic paper writing (AAAI, IJCAI, IEEE) |
| `/browse` | Headless browser for QA testing |
| `/qa` | Systematic QA testing and bug fixing |
| `/debug` | Systematic debugging with root cause investigation |
| `/design-review` | Visual QA and design polish |
| `/ship` | Ship workflow (merge, test, PR creation) |
| `/retro` | Weekly engineering retrospective |
| `/office-hours` | YC-style startup consulting |
| `/brief-write` | Concise writing style |
| `/humanizer` | Humanize AI-generated text |
| `/power-iterate` | Continuous autonomous iteration |
| `/skill-refiner` | Improve and refine skills |

## Architecture

```
openlaoke/
├── core/                      # Core systems
│   ├── state.py              # Centralized state management
│   ├── tool.py               # Tool base class and registry
│   ├── multi_provider_api.py # Multi-provider API client
│   ├── repl.py               # REPL interaction loop
│   ├── config_wizard.py      # Configuration wizard
│   ├── prompt_input.py       # Prompt input with Ctrl+P picker
│   ├── system_prompt.py      # System prompt builder (compact for local)
│   ├── local_model_manager.py # Local GGUF model registry & download
│   ├── builtin_model_provider.py # llama-cpp-python inference provider
│   ├── model_cli.py          # CLI model management commands
│   ├── distilled_templates.py # Distilled prompt templates
│   ├── small_model_optimizations.py # Small model optimizations (type coercion, schema sanitization, output compression)
│   ├── hook_system.py        # 15-hook extension system
│   ├── bitter_lesson_tracker.py # Self-reflection and strategy tracking
│   ├── cross_project_lessons.py # Cross-project lessons learned database
│   ├── compact/              # Context compression system
│   │   ├── fast_pruner.py    # Pure-algorithm context pruning (<5ms)
│   │   ├── strategies.py     # Compaction strategies
│   │   └── summarizer.py     # LLM-based summarization
│   ├── supervisor/           # Task supervision system
│   ├── model_assessment/     # Model capability assessment
│   ├── hyperauto/            # HyperAuto mode
│   ├── skill_system.py       # Skill management
│   └── memory/               # Persistent memory
├── tools/                    # Tool implementations (30+)
├── commands/                 # Slash commands (20+)
├── types/                    # Type definitions
├── services/mcp/             # MCP services
├── server/                   # Web API and UI
├── utils/                    # Utilities
├── hooks/                    # Hook implementations
└── entrypoints/cli.py        # CLI entry point
```

## Running Modes

### Online Mode (Default)
```bash
openlaoke
```
Direct API calls to cloud providers. Best for GPT-4o, Claude 4, etc.

### Local Mode
```bash
openlaoke --local
```
Atomic task decomposition + supervision. Best for small local models.

### Web UI
```bash
openlaoke web --host 0.0.0.0 --port 8080
```
Full web interface with LAN access.

### API Server
```bash
openlaoke server
```
FastAPI backend at localhost:3000.

## Command Line Options

```bash
# Non-interactive mode
openlaoke "Write a Python script that sorts a list"

# Specify model and provider
openlaoke -m gpt-4o --provider openai
openlaoke --provider ollama -m llama3.2

# Use proxy
openlaoke --proxy http://127.0.0.1:7890

# Set working directory
openlaoke --cwd /path/to/project

# Resume last session
openlaoke --resume

# Reconfigure
openlaoke --config

# Local mode for small models
openlaoke --local --provider ollama -m gemma3:1b
```

## Configuration

Config stored at `~/.openlaoke/config.json`:

```json
{
  "providers": {
    "active_provider": "local_builtin",
    "active_model": "custom:unsloth-Qwen3.5-0.8B-GGUF",
    "local_n_ctx": 262144,
    "local_temperature": 0.3,
    "local_repetition_penalty": 1.1,
    "providers": {
      "local_builtin": {
        "default_model": "custom:unsloth-Qwen3.5-0.8B-GGUF",
        "enabled": true
      },
      "ollama": {
        "base_url": "http://localhost:11434/v1",
        "default_model": "gemma3:1b",
        "enabled": true
      }
    }
  },
  "proxy_mode": "none",
  "max_tokens": 8192,
  "temperature": 1.0,
  "theme": "dark"
}
```

Custom models registered at `~/.openlaoke/models/custom_models.json`. Sessions at `~/.openlaoke/sessions/`.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `MINIMAX_API_KEY` | MiniMax API key |
| `ALIYUN_API_KEY` | Aliyun Coding Plan API key |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key |
| `GOOGLE_API_KEY` | Google AI API key |
| `XAI_API_KEY` | xAI API key |
| `MISTRAL_API_KEY` | Mistral API key |
| `GROQ_API_KEY` | Groq API key |
| `CEREBRAS_API_KEY` | Cerebras API key |
| `COHERE_API_KEY` | Cohere API key |
| `DEEPINFRA_API_KEY` | DeepInfra API key |
| `TOGETHERAI_API_KEY` | Together AI API key |
| `PERPLEXITY_API_KEY` | Perplexity API key |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `GITHUB_TOKEN` | GitHub Personal Access Token |
| `OPENLAOKE_MODEL` | Default model |
| `HTTP_PROXY` / `HTTPS_PROXY` | Proxy settings |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Lint and format
ruff check . && ruff format .

# Type check
mypy

# Run tests
pytest
pytest --cov
pytest tests/test_tools.py::TestBashTool::test_simple_command

# Build package
python -m build
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

GPLv3
