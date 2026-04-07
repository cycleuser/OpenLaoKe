# OpenLaoKe Project Analysis Report

## 1. Project Overview

**OpenLaoKe** is an open-source terminal AI coding assistant that supports multiple LLM providers. It's designed as a Python package with a modular architecture supporting tools, commands, skills, and multi-provider API integration.

- **Version**: 0.1.6
- **Build Time**: 2026-04-03
- **Total Lines of Code**: ~48,835 (including tests and examples)
- **Core Python Lines**: ~40,735

---

## 2. Main Entry Points

### Primary Entry Point
**File**: `openlaoke/__main__.py` (Lines 1-7)
```python
"""CLI entry point for python -m openlaoke."""
from openlaoke.entrypoints.cli import main

if __name__ == "__main__":
    main()
```

### CLI Entry Point
**File**: `openlaoke/entrypoints/cli.py` (Lines 24-350)

The CLI provides two modes:
1. **Interactive Mode**: Starts REPL loop (`openlaoke`)
2. **Non-Interactive Mode**: Execute single prompt (`openlaoke "your prompt"`)

**Key CLI Options** (Lines 29-147):
- `-v, --version`: Show version
- `-m, --model`: Specify model (e.g., gpt-4o, llama3.2)
- `-p, --permission`: Permission mode (default/auto/bypass)
- `-y, --yes`: Auto-approve all tool calls
- `--provider`: AI provider selection (anthropic, openai, ollama, minimax, etc.)
- `--api-key`: API key override
- `--base-url`: Custom API endpoint
- `--proxy`: Proxy URL
- `--max-tokens`: Response token limit
- `--thinking-budget`: Extended thinking budget
- `--config`: Run configuration wizard
- `server --host --port`: Start HTTP API server

---

## 3. Python File Structure by Purpose

### Core System (openlaoke/core/)
| File | Purpose | Key Classes/Functions |
|------|---------|----------------------|
| `api.py` (318 lines) | Anthropic API client | `APIClient`, `APIConfig`, `ModelPricing` |
| `multi_provider_api.py` (969 lines) | Multi-provider support | `MultiProviderClient` - 20+ providers |
| `state.py` (227 lines) | Application state | `AppState`, `SessionConfig` |
| `repl.py` (522 lines) | REPL loop | `REPL` class - main interaction |
| `tool.py` (271 lines) | Tool base system | `Tool`, `ToolRegistry`, `ToolContext` |
| `system_prompt.py` | System prompt builder | `build_system_prompt()` |
| `task.py` | Task management | `TaskManager` |
| `skill_system.py` (303 lines) | Skill loading | `Skill`, `SkillRegistry` |

### Subsystems (openlaoke/core/)

#### Compact System (compact/)
- `compactor.py` - Conversation compression
- `strategies.py` - Compression strategies
- `summarizer.py` - Content summarization
- `token_budget.py` - Token budget management

#### Explorer System (explorer/)
- `explorer.py` - Code exploration
- `discovery.py` - Project discovery
- `architecture.py` - Architecture analysis
- `hypothesis.py` - Hypothesis generation
- `reasoning.py` - Reasoning engine

#### HyperAuto System (hyperauto/)
- `agent.py` - Autonomous agent
- `workflow.py` - Workflow orchestration
- `skill_generator.py` - Skill generation
- `decision_engine.py` - Decision making
- `reflection.py` - Self-reflection
- `learning.py` - Learning system
- `validator.py` - Validation
- `test_runner.py` - Test execution

#### Memory System (memory/)
- `memory.py` - Long-term memory
- `embedding.py` - Embedding generation
- `knowledge_graph.py` - Knowledge graph
- `retrieval.py` - Memory retrieval
- `consolidation.py` - Memory consolidation

#### Multi-Agent System (multi_agent/)
- `coordinator.py` - Agent coordination
- `agent_pool.py` - Agent pool management
- `communication.py` - Inter-agent communication
- `task_distribution.py` - Task distribution
- `conflict_resolution.py` - Conflict resolution
- `team.py` - Team management

#### Query System (query/)
- `engine.py` - Query engine
- `stream.py` - Streaming responses
- `events.py` - Event handling
- `recovery.py` - Error recovery
- `context.py` - Query context

#### Scheduler System (scheduler/)
- `scheduler.py` - Task scheduling
- `executor.py` - Task execution
- `priority.py` - Priority management
- `timeout.py` - Timeout handling

#### Supervisor System (supervisor/)
- `supervisor.py` - Task supervision
- `checker.py` - Completion checking
- `requirements.py` - Requirement tracking

#### Middleware System (middleware/)
- `base.py` - Middleware base
- `chain.py` - Middleware chain
- `builtins.py` - Built-in middleware
- `context.py` - Middleware context

#### Tools Subsystem (tools/)
- `deferred_registry.py` - Deferred tool loading
- `lazy_loader.py` - Lazy loading utilities
- `tool_discovery.py` - Tool discovery
- `tool_search.py` - Tool search

---

## 4. Tool System Architecture

### Base Tool Class
**File**: `openlaoke/core/tool.py` (Lines 37-110)

```python
class Tool(ABC):
    """Base class for all tools."""
    
    name: str = "base_tool"
    description: str = ""
    input_schema: type[BaseModel] | dict[str, Any] = {}
    task_type: TaskType = TaskType.LOCAL_BASH
    is_read_only: bool = False
    is_destructive: bool = False
    is_concurrency_safe: bool = True
    requires_approval: bool = False
    
    @abstractmethod
    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        """Execute the tool with the given input."""
        ...
```

### Tool Registry (Lines 128-271)
**Features**:
- Lazy loading support
- Deferred tool registration
- Async tool loading with locks
- Tool search functionality

```python
class ToolRegistry:
    def register(self, tool: Tool) -> None
    def register_deferred(self, name: str, loader: Callable) -> None
    def get(self, name: str) -> Tool | None
    async def get_async(self, name: str) -> Tool | None
    def get_all_for_prompt(self) -> list[dict[str, Any]]
```

### Tool Registration
**File**: `openlaoke/tools/register.py` (Lines 10-193)

**Essential Tools** (Loaded immediately):
1. `Bash` - Shell command execution
2. `Read` - File reading
3. `Write` - File writing
4. `Edit` - File editing
5. `Glob` - File pattern matching
6. `Grep` - Regex search

**Deferred Tools** (Lazy loaded):
- Agent, ApplyPatch, Batch, Git, ListDirectory, LSP
- NotebookWrite, Plan, Question, TaskKill, TodoWrite
- WebFetch, WebSearch, Sleep, Brief, WebBrowser
- Tmux, PowerShell, Cron, REPL, ToolSearch
- DownloadReference, BatchDownloadReferences, SearchAndDownloadPapers

### Tool Files (openlaoke/tools/)
| File | Lines | Purpose |
|------|-------|---------|
| `bash_tool.py` | 127 | Shell command execution with safety classification |
| `read_tool.py` | 128 | File reading with encoding detection |
| `write_tool.py` | ~80 | File writing |
| `edit_tool.py` | ~100 | Targeted file editing |
| `glob_tool.py` | ~60 | Glob pattern matching |
| `grep_tool.py` | ~80 | Regex content search |
| `agent_tool.py` | ~150 | Sub-agent spawning |
| `git_tool.py` | ~100 | Git operations |
| `web_browser_tool.py` | ~200 | Browser automation (Playwright) |
| `webfetch_tool.py` | ~80 | URL fetching |
| `websearch_tool.py` | ~60 | DuckDuckGo search |

### Permission System
**File**: `openlaoke/types/permissions.py`

```python
class PermissionMode(StrEnum):
    DEFAULT = "default"  # Ask for dangerous operations
    AUTO = "auto"        # Auto-approve safe operations
    BYPASS = "bypass"    # No restrictions
```

**Bash Safety Classification** (`openlaoke/utils/permissions/bash_classifier.py`):
- SAFE: Read-only commands (ls, cat, grep)
- MODERATE: Minor modifications (mkdir, touch)
- DANGEROUS: Significant changes (rm, mv, chmod)
- DESTRUCTIVE: Irreversible (rm -rf, dd, mkfs)

---

## 5. LLM Integration Code

### Multi-Provider API Client
**File**: `openlaoke/core/multi_provider_api.py` (Lines 77-969)

**Supported Providers** (20+):
1. **Anthropic** - Claude models (Sonnet, Opus, Haiku)
2. **OpenAI** - GPT-4o, GPT-4-turbo, o1
3. **MiniMax** - M2.7, M2.5 series
4. **Aliyun Coding Plan** - Qwen, Kimi, GLM
5. **Ollama** - Local models (gemma3, llama3.2)
6. **LM Studio** - Local models
7. **Azure OpenAI** - Azure-hosted GPT
8. **Google/Gemini** - Gemini 2.0, 1.5
9. **Google Vertex** - Vertex AI
10. **AWS Bedrock** - Claude on AWS
11. **XAI** - Grok models
12. **Mistral** - Mistral Large, Codestral
13. **Groq** - Fast inference
14. **Cerebras** - Llama on Cerebras
15. **Cohere** - Command R+
16. **DeepInfra** - Open-source models
17. **TogetherAI** - Multi-model hosting
18. **Perplexity** - Online search models
19. **OpenRouter** - Multi-provider gateway
20. **GitHub Copilot** - GitHub's AI

**Key Methods** (Lines 518-676):
```python
async def send_message(
    self,
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    model: str | None = None,
    max_tokens: int = 8192,
    temperature: float = 1.0,
    thinking_budget: int = 0,
) -> tuple[AssistantMessage, TokenUsage, CostInfo]

async def stream_message(...) -> AsyncIterator[tuple[str, TokenUsage | None, CostInfo | None]]
```

**Format Conversion**:
- `_convert_to_anthropic_format()` (Lines 301-376)
- `_convert_to_openai_format()` (Lines 378-422)
- `_convert_to_google_format()` (Lines 754-776)
- `_convert_to_cohere_format()` (Lines 913-934)

**Model Pricing** (Lines 35-74):
```python
MODEL_PRICES: dict[str, ModelPricing] = {
    "claude-sonnet-4-20250514": ModelPricing(3.0, 15.0, 0.30, 3.75),
    "gpt-4o": ModelPricing(2.5, 10.0, 0.0, 0.0),
    # ... 40+ models with pricing
}
```

---

## 6. CLI Interface Design

### Command Structure
**File**: `openlaoke/commands/base.py` (Lines 35-854)

**Base Command Pattern**:
```python
class SlashCommand(ABC):
    name: str = ""
    description: str = ""
    aliases: list[str] = []
    hidden: bool = False
    
    @abstractmethod
    async def execute(self, ctx: CommandContext) -> CommandResult:
        ...
```

**Available Commands** (25+):
| Command | Aliases | Purpose |
|---------|---------|---------|
| `/help` | `/?` | Show available commands |
| `/exit` | `/quit`, `/q` | Exit OpenLaoKe |
| `/clear` | - | Clear screen/conversation |
| `/model` | - | Change model |
| `/permission` | - | Change permission mode |
| `/compact` | - | Compact conversation |
| `/cost` | - | Show session cost |
| `/cwd` | - | Change working directory |
| `/resume` | - | Resume last session |
| `/settings` | - | Show current settings |
| `/doctor` | - | Run diagnostics |
| `/init` | - | Create AGENTS.md |
| `/mcp` | - | Manage MCP servers |
| `/theme` | - | Set terminal theme |
| `/vim` | - | Toggle Vim mode |
| `/hooks` | - | Manage hooks |
| `/export` | - | Export session (JSON/Markdown) |
| `/usage` | - | Detailed usage stats |
| `/memory` | - | Manage long-term memory |
| `/agents` | - | Show agent types |
| `/undo` | `/revert` | Restore file version |
| `/history` | - | File modification history |

### REPL Implementation
**File**: `openlaoke/core/repl.py` (Lines 32-522)

**Core Flow**:
```
run() → _handle_input() → _handle_chat() → _run_api_loop() → _execute_tool()
```

**Key Features**:
1. **Skill Activation** (Lines 94-117): Detect `/skillname` and load from SKILL.md
2. **Command Parsing** (Lines 119-123): Parse slash commands
3. **API Loop** (Lines 268-390): Send messages, handle responses, execute tools
4. **Tool Execution** (Lines 392-472): Permission checks, validation, execution
5. **Supervisor Integration** (Lines 158-239): Task completion checking with retry

---

## 7. Key Design Patterns

### 1. Registry Pattern
**Files**: 
- `openlaoke/core/tool.py` - `ToolRegistry`
- `openlaoke/core/skill_system.py` - `SkillRegistry`
- `openlaoke/commands/registry.py` - Command registry

**Pattern**: Centralized registration with lookup capabilities
```python
class ToolRegistry:
    _tools: dict[str, Tool]
    _deferred_loaders: dict[str, Callable]
    
    def register(self, tool: Tool) -> None
    def get(self, name: str) -> Tool | None
```

### 2. Abstract Base Class Pattern
**Files**: 
- `openlaoke/core/tool.py` - `Tool(ABC)`
- `openlaoke/commands/base.py` - `SlashCommand(ABC)`

**Pattern**: Define interface, subclasses implement specifics
```python
class Tool(ABC):
    @abstractmethod
    async def call(self, ctx: ToolContext, **kwargs) -> ToolResultBlock:
        ...
```

### 3. Lazy Loading Pattern
**Files**:
- `openlaoke/tools/register.py` - Deferred tool loading
- `openlaoke/core/tools/lazy_loader.py`

**Pattern**: Load resources only when needed
```python
registry.register_deferred_with_info(
    name="Agent",
    loader=lambda: __import__("...").AgentTool(),
    description="...",
    search_hint="...",
)
```

### 4. Context Object Pattern
**Files**:
- `openlaoke/core/tool.py` - `ToolContext`
- `openlaoke/commands/base.py` - `CommandContext`

**Pattern**: Bundle related data into single object
```python
@dataclass
class ToolContext:
    app_state: AppState
    tool_use_id: str
    agent_id: str | None = None
    abort_signal: Any = None
```

### 5. Dataclass Pattern
**Files**:
- `openlaoke/types/core_types.py` - All type definitions
- `openlaoke/core/state.py` - `AppState`

**Pattern**: Typed data containers with minimal boilerplate
```python
@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    # ... with methods
```

### 6. Observer Pattern
**File**: `openlaoke/core/state.py` (Lines 148-160)

**Pattern**: State change notifications
```python
class AppState:
    _listeners: list[Callable[[AppState], None]]
    
    def subscribe(self, listener: Callable) -> None
    def _notify(self) -> None:
        for listener in self._listeners:
            listener(self)
```

### 7. Strategy Pattern
**Files**:
- `openlaoke/core/compact/strategies.py`
- `openlaoke/core/explorer/exploration_strategy.py`

**Pattern**: Pluggable algorithms
```python
class CompactionStrategy(ABC):
    @abstractmethod
    def compact(self, messages: list[Message]) -> list[Message]:
        ...
```

### 8. Middleware/Chain of Responsibility
**Files**: `openlaoke/core/middleware/`

**Pattern**: Processing pipeline
```python
class Middleware(ABC):
    async def process(self, context: MiddlewareContext) -> MiddlewareResult:
        ...

class MiddlewareChain:
    def add(self, middleware: Middleware) -> None
    async def execute(self, context: MiddlewareContext) -> MiddlewareResult:
        ...
```

### 9. Pydantic Validation Pattern
**Files**: All tool input schemas

**Pattern**: Schema validation using Pydantic
```python
class BashInput(BaseModel):
    command: str = Field(description="The bash command to execute")
    description: str = Field(default="", description="Brief description")
    timeout: float | None = Field(default=None, description="Timeout in seconds")
```

### 10. Factory Pattern
**File**: `openlaoke/core/state.py` (Lines 210-226)

**Pattern**: Centralized object creation
```python
def create_app_state(
    cwd: str | None = None,
    model: str = "claude-sonnet-4-20250514",
    persist_path: str | None = None,
    **kwargs: Any,
) -> AppState:
    """Factory for creating AppState with sensible defaults."""
    session_id = f"session_{int(time.time())}"
    state = AppState(session_id=session_id, ...)
    return state
```

---

## 8. Type System Architecture

**File**: `openlaoke/types/core_types.py` (339 lines)

### Core Enums
```python
class PermissionMode(StrEnum): DEFAULT, AUTO, BYPASS
class PermissionResult(StrEnum): ALLOW, DENY, ASK
class TaskType(StrEnum): LOCAL_BASH, LOCAL_AGENT, REMOTE_AGENT, ...
class TaskStatus(StrEnum): PENDING, RUNNING, COMPLETED, FAILED, KILLED
class MessageRole(StrEnum): USER, ASSISTANT, SYSTEM
```

### Core Data Structures
```python
ToolUseBlock: Tool request from model
ToolResultBlock: Tool execution result
UserMessage: User input
AssistantMessage: Model response
TaskState: Task runtime state
TokenUsage: Token tracking
CostInfo: Cost tracking
```

### Provider Types
**File**: `openlaoke/types/providers.py` (394 lines)

```python
class ProviderType(StrEnum): 20+ provider types
class ProviderConfig: Single provider configuration
class MultiProviderConfig: All providers configuration
class CodingPlan: Coding plan configuration
class PlanConfig: Plan management
```

---

## 9. Server Mode

**File**: `openlaoke/server/server.py`

HTTP API server for remote access:
```python
class Server:
    host: str = "localhost"
    port: int = 3000
    cors_origins: list[str] | None = None
    
    def run(self) -> None:
        # Start HTTP server
```

---

## 10. Configuration System

**File**: `openlaoke/utils/config.py`

Configuration stored at `~/.openlaoke/`:
- `config.json` - Main configuration
- `mcp_servers.json` - MCP server definitions
- `sessions/` - Session persistence
- `memory.json` - Long-term memory
- `file_history/` - File modification history

**Config Wizard**: `openlaoke/core/config_wizard.py`
- First-run setup
- Provider selection
- API key input
- Model selection

---

## Summary

OpenLaoKe is a well-architectured AI coding assistant with:

1. **Modular Design**: Clear separation of concerns (core, tools, commands, types)
2. **Extensible Tool System**: Abstract base class + registry with lazy loading
3. **Multi-Provider Support**: 20+ LLM providers with unified interface
4. **Rich CLI**: Interactive REPL + 25+ slash commands
5. **Safety First**: Permission modes, command classification, validation
6. **Advanced Features**: Skills, memory, supervisor, multi-agent, middleware
7. **Modern Patterns**: Dataclasses, Pydantic, async/await, type hints throughout

The codebase demonstrates professional Python practices with comprehensive type safety, clear documentation, and extensible architecture.