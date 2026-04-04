# OpenLaoKe

Open-source terminal AI coding assistant with advanced automation and supervision capabilities.

## Features

### Core Features
- **Interactive REPL** with rich terminal UI
- **Command History** - Use ↑/↓ arrows to browse previous commands, Ctrl+R to search
- **Smart Autocomplete** - Tab completion for commands and skills
- **Multi-Provider Support** - 22 AI providers supported
- **Tool System** - 30+ built-in tools
- **MCP Support** - Connect to external MCP tool servers
- **Permission System** - Three modes: default, auto, bypass
- **Session Persistence** - Auto-save and resume sessions
- **Cost Tracking** - Real-time token usage and cost display
- **Slash Commands** - 20+ built-in commands
- **Hook System** - Extensible pre/post hooks
- **Proxy Support** - No proxy, system proxy, or custom proxy

### Advanced Features
- **HyperAuto Mode** - Fully autonomous operation with self-improvement
- **Task Supervision** - Automatic retry and completion verification
- **Model Assessment** - Adaptive task decomposition based on model capabilities
- **Anti-AI Detection** - Ensure generated content appears human-written
- **Reference Download** - Automatic PDF download for academic writing
- **Skill System** - YAML-based skill system with dynamic loading

## Supported Providers (22)

| Provider | Type | API Key Required | Models |
|----------|------|------------------|--------|
| Anthropic | Cloud | Yes | Claude 4 Sonnet, Claude 4 Opus, Claude 3.5 Sonnet/Haiku |
| OpenAI | Cloud | Yes | GPT-4o, GPT-4o-mini, GPT-4-turbo, o1-preview, o1-mini |
| MiniMax | Cloud | Yes | MiniMax-M2.7, MiniMax-M2.5, MiniMax-M2.1 |
| Aliyun Coding Plan | Cloud | Yes | Qwen3.5-plus, Kimi-k2.5, GLM-5, Qwen3-max |
| Azure OpenAI | Cloud | Yes | GPT-4o, GPT-4o-mini, GPT-4-turbo, GPT-35-turbo |
| Google AI | Cloud | Yes | Gemini 2.0 Flash/Pro, Gemini 1.5 Flash/Pro |
| Google Vertex AI | Cloud | Yes | Gemini models via GCP |
| AWS Bedrock | Cloud | Yes | Claude 3.5, Llama 3.1, Amazon Nova |
| xAI Grok | Cloud | Yes | Grok-2-latest, Grok-beta, Grok-vision-beta |
| Mistral AI | Cloud | Yes | Mistral-large, Mistral-small, Codestral |
| Groq | Cloud | Yes | Llama 3.3 70B, Llama 3.1 8B, Mixtral 8x7B |
| Cerebras | Cloud | Yes | Llama 3.3 70B, Llama 3.1 8B/70B |
| Cohere | Cloud | Yes | Command-r-plus, Command-r, Command |
| DeepInfra | Cloud | Yes | Llama 3.3/3.1, Mistral-small |
| Together AI | Cloud | Yes | Llama 3.3/3.1, Mistral, Qwen 2.5 |
| Perplexity | Cloud | Yes | Sonar models (online/chat) |
| OpenRouter | Cloud | Yes | Multi-provider access (Claude, GPT-4, Gemini, Llama) |
| GitHub Copilot | Cloud | Yes | GPT-4o, GPT-4o-mini, o1-preview, o1-mini |
| Ollama | Local | No | Gemma 3/4, Llama 3.1/3.2, CodeLlama, Qwen 2.5, DeepSeek |
| LM Studio | Local | No | Any local model |
| OpenAI-Compatible | Custom | Optional | Any OpenAI-compatible endpoint |

## Tool System (30+ Tools)

### File Operations
- **Read** - Read file contents with line range support
- **Write** - Create/overwrite files
- **Edit** - Targeted find-and-replace with diff output
- **Glob** - Fast file pattern matching (respects .gitignore)
- **Grep** - Regex search across files
- **LS** - List directory contents

### Code Intelligence
- **LSP** - Language Server Protocol integration
- **Git** - Git operations (status, diff, log, blame)
- **Bash** - Execute shell commands with streaming output

### Web & Search
- **WebSearch** - Search the web for information
- **WebFetch** - Fetch web page content
- **SearchAndDownloadPapers** - Search academic papers

### Reference Management
- **DownloadReference** - Download single PDF reference
- **BatchDownloadReferences** - Download multiple references
- **ReferenceManager** - Manage reference library

### Task Management
- **TodoWrite** - Manage task lists
- **Taskkill** - Kill running tasks
- **Batch** - Execute multiple tools in parallel
- **Agent** - Spawn sub-agents for parallel work

### Notebook Support
- **NotebookWrite** - Write Jupyter notebook cells
- **NotebookRead** - Read notebook contents

### System & Utilities
- **Cron** - Schedule tasks
- **Memory** - Store and retrieve information
- **Hook** - Configure hooks

## Slash Commands

### Model & Provider Management
| Command | Description | Examples |
|---------|-------------|----------|
| `/model` | Show current model and available models | `/model` |
| `/model <name>` | Switch to specific model | `/model gpt-4o` |
| `/model <1-N>` | Select model by index | `/model 1` or `/model #3` |
| `/model <provider>/<model>` | Switch provider and model | `/model ollama/gemma3:27b` |
| `/model -l` | List all models from all providers | `/model -l` |
| `/model -p` | List all providers | `/model -p` |
| `/provider` | Show current provider | `/provider` |
| `/provider <name>` | Switch to different provider | `/provider ollama` |

### Session Management
| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/exit` | Exit OpenLaoKe |
| `/clear` | Clear screen and conversation |
| `/resume` | Resume last session |
| `/compact` | Compact conversation to save context |

### Configuration
| Command | Description |
|---------|-------------|
| `/permission [mode]` | Change permission mode (default/auto/bypass) |
| `/settings` | Show current settings |
| `/theme [name]` | Change color theme |
| `/cwd [path]` | Show or change working directory |

### Information
| Command | Description |
|---------|-------------|
| `/cost` | Show session cost and token usage |
| `/usage` | Show detailed usage statistics |
| `/commands` | Show example commands |
| `/doctor` | Diagnose configuration issues |
| `/hooks` | Manage hooks |
| `/mcp` | Manage MCP servers |

### Advanced
| Command | Description |
|---------|-------------|
| `/hyperauto` | Start HyperAuto mode (autonomous operation) |
| `/skill <name>` | Execute a skill |
| `/memory` | Manage persistent memory |
| `/agents` | Manage sub-agents |

## Installation

```bash
# Clone and install
git clone https://github.com/cycleuser/OpenLaoKe.git
cd OpenLaoKe
pip install -e .

# Or with uv (recommended)
uv pip install -e ".[dev]"
```

## Usage

### First Run
```bash
# First run shows configuration wizard
openlaoke

# Reconfigure
openlaoke --config
```

### Command Line Options
```bash
# Non-interactive mode
openlaoke "Write a Python script that sorts a list"

# Specify model and permission
openlaoke -m gpt-4o -p auto
openlaoke --provider ollama -m llama3.2

# Use proxy
openlaoke --proxy http://127.0.0.1:7890

# Set working directory
openlaoke --cwd /path/to/project

# Resume last session
openlaoke --resume
```

### Model Selection

#### Interactive Selection
```
OpenLaoKe: /model
Current provider: aliyun_coding_plan
Current model: glm-5

Available models (aliyun_coding_plan):
  [1] qwen3.5-plus
  [2] kimi-k2.5
  [3] glm-5 (current)
  [4] MiniMax-M2.5
  [5] qwen3-max-2026-01-23
  [6] qwen3-coder-next
  [7] qwen3-coder-plus
  [8] glm-4.7

Usage:
  /model <name>        - Switch to specific model
  /model <1-8>         - Select by index number
  /model #<1-8>        - Select by index (with # prefix)
  /model <provider>/<model> - Switch provider and model
  /model -l            - List all models from all providers
  /model -p            - List all providers
```

#### Quick Switch Examples
```bash
# Switch by name
/model gpt-4o

# Switch by index
/model 1
/model #3

# Switch provider and model together
/model ollama/gemma3:27b
/model anthropic/claude-sonnet-4

# Switch provider only
/provider ollama
```

### Provider Configuration

The configuration wizard supports:
- **Stored configuration reuse** - Detects and offers to use existing API keys
- **Environment variables** - Automatically detects API keys in environment
- **Multiple profiles** - Configure multiple providers and switch between them

```
Step 1: Choose your AI provider

   [1]   Anthropic                   needs setup
   [2]   OpenAI (GPT-4)              needs setup
   [3]   MiniMax                     ✓ stored
   [4]   Aliyun Coding Plan          ✓ stored
   [19]  Ollama (Local)              ✓ local
   [20]  LM Studio (Local)           ✓ local
   [21]  OpenAI-Compatible (Custom)  ✓ stored

Select provider [1-22] (19): 4

Configuring aliyun_coding_plan

   [1]  Stored config  Key: sk-sp-f9...0e3f, Model: glm-5
   [2]  Reconfigure    Enter new API key and settings

Select configuration source [1/2] (1): 1
✓ Using stored configuration for aliyun_coding_plan
```

## Advanced Features

### HyperAuto Mode

Fully autonomous operation with self-improvement capabilities:

```bash
/hyperauto on
/hyperauto --mode autonomous
/hyperauto --timeout 3600
```

Features:
- **Automatic task decomposition** - Breaks complex tasks into subtasks
- **Self-verification** - Verifies completion and quality
- **Adaptive learning** - Learns from failures and improves
- **Skill generation** - Creates new skills on demand
- **Project initialization** - Analyzes and sets up new projects

### Task Supervision

Automatic retry and completion verification:

- **Requirement parsing** - Extracts verifiable requirements from user requests
- **Progress monitoring** - Tracks completion percentage
- **Quality checking** - Anti-AI detection, reference verification
- **Automatic retry** - Retries with specific feedback
- **Escalation** - Alerts when automatic recovery fails

### Model Assessment

Adaptive task decomposition based on model capabilities:

**Tier System:**
- **Tier 1 (Advanced)**: Claude 4, GPT-4o - Complex tasks, minimal verification
- **Tier 2 (Capable)**: Claude 3.5 Haiku, GPT-4o-mini, Gemma3 27B - Moderate complexity
- **Tier 3 (Moderate)**: Gemma3 12B, Llama 3.1 8B, Qwen 2.5 14B - Limited subtasks
- **Tier 4 (Basic)**: Gemma3 4B, Llama 3.2 3B - Atomic operations, frequent verification
- **Tier 5 (Limited)**: Gemma3 1B, Llama 3.2 1B - Very simple tasks, step-by-step guidance

**Automatic Adaptation:**
```python
# Small model (gemma3:1b) - Tasks broken into atomic steps
Task: "Write an article and create a diagram"
Decomposed:
  Step 1: Write an article
  Step 2: create a diagram
Verification: every_step
Max subtasks: 4
Retry limit: 8

# Advanced model (claude-sonnet-4) - Handles as single task
Task: "Write an article and create a diagram"
Decomposed: [single task]
Verification: minimal
Max subtasks: 20
```

### Anti-AI Detection

Ensures generated content appears human-written:

**Detection Patterns:**
- Numbered lists without substance
- Vague claims without evidence
- Generic phrases ("Systems could enable:")
- Lack of specific citations
- Missing technical depth

**Enforcement:**
- Mandatory real citations with downloadable PDFs
- Specific numbers and measurements required
- Code references with line numbers
- Complete paragraphs, not fragmented lists
- Technical depth (HOW and WHY, not just WHAT)

### Reference Download

Automatic PDF download for academic writing:

```
OpenLaoKe: Write an academic paper about LLM efficiency

[Auto-downloading references to pdf/ directory]
✓ Downloaded: attention-is-all-you-need.pdf
✓ Downloaded: llama-2-open-foundation.pdf
✓ Downloaded: mixtral-of-experts.pdf

[Writing paper with proper citations...]
```

Commands:
```
/download-ref <URL>           - Download single reference
/download-refs <URLs...>      - Download multiple references
/search-papers <query>        - Search and download papers
```

### Skill System

YAML-based skills for specialized workflows:

**Available Skills (38+):**
- `/academic-writer` - Academic paper writing
- `/browse` - Headless browser for QA testing
- `/qa` - Systematic QA testing and bug fixing
- `/debug` - Systematic debugging with root cause investigation
- `/design-review` - Visual QA and design polish
- `/ship` - Ship workflow (merge, test, PR creation)
- `/retro` - Weekly engineering retrospective
- `/office-hours` - YC-style startup consulting
- `/brief-write` - Concise writing style
- `/humanizer` - Humanize AI-generated text
- `/power-iterate` - Continuous autonomous iteration
- `/skill-refiner` - Improve and refine skills

**Usage:**
```bash
# Use a skill
/browse https://example.com

# List all skills
/skill --list

# Get skill help
/skill academic-writer --help
```

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

## Architecture

```
openlaoke/
├── core/                      # Core systems
│   ├── state.py              # Centralized state management
│   ├── tool.py               # Tool base class and registry
│   ├── task.py               # Task lifecycle management
│   ├── multi_provider_api.py # Multi-provider API client
│   ├── repl.py               # REPL interaction loop
│   ├── config_wizard.py      # Configuration wizard
│   ├── supervisor/           # Task supervision system
│   ├── model_assessment/     # Model capability assessment
│   ├── hyperauto/            # HyperAuto mode
│   ├── skill_system.py       # Skill management
│   └── memory/               # Persistent memory
├── tools/                    # Tool implementations (30+)
├── commands/                 # Slash commands (20+)
├── types/                    # Type definitions
├── services/                 # External services (MCP)
├── components/               # UI components (TUI)
├── utils/                    # Utilities
├── hooks/                    # Hook implementations
└── entrypoints/              # CLI entry point
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run linter
ruff check .
ruff check . --fix

# Format code
ruff format .

# Type check
mypy

# Run tests
pytest
pytest --cov
pytest tests/test_tools.py::TestBashTool::test_simple_command

# Build package
python -m build
```

## Configuration

User config is stored at `~/.openlaoke/config.json`:

```json
{
  "providers": {
    "active_provider": "ollama",
    "active_model": "gemma3:1b",
    "providers": {
      "ollama": {
        "api_key": "",
        "base_url": "http://localhost:11434/v1",
        "default_model": "gemma3:1b",
        "enabled": true
      }
    }
  },
  "proxy_mode": "none",
  "proxy_url": "",
  "max_tokens": 8192,
  "temperature": 1.0,
  "theme": "dark"
}
```

Session files are stored at `~/.openlaoke/sessions/`

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

GPLv3