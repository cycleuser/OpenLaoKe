# Changelog

All notable changes to OpenLaoKe will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.43] - 2026-09-19

### Fixed
- **Local thinking models no longer reason without bound**: when thinking was not
  explicitly requested, requests to local providers now send
  `reasoning_effort: "none"`. `qwen3.5:2b` previously spent minutes per turn
  reasoning (and often burned the whole token budget before emitting any tool
  call); it now answers in seconds.
- **Local context budget now uses the server's real window**: the budget came from
  the models.dev catalog (256k for `qwen3.5:2b`) while Ollama serves
  `num_ctx=16384`, so pruning never ran, prompts grew past the real window, and
  prefills slowed until they hit the 300s read timeout (“Model returned no
  output”). `get_effective_context_limit()` now reads Ollama's `/api/ps` and
  budgets against the runtime window (falling back to 8k when unknown); cloud
  providers keep the catalog value.

## [0.1.42] - 2026-09-19

### Fixed
- **Command execution was over-blocked**: AUTO mode now stops only high-confidence
  dangerous commands (`rm -rf`, `curl | sh`, inline interpreter code, file-writing
  redirections); unknown commands run. The safe list gained macOS/Linux
  system-inspection tools (`lscpu`, `vm_stat`, `sysctl`, `system_profiler`,
  `sw_vers`, `ioreg`, `hostinfo`, `defaults`, …).
- **System paths are readable again**: `Read` / `Glob` / `Grep` may read `/proc`,
  `/etc`, `/sys`, `/usr`, `/Library`, … while `Write` / `Edit` stay confined to
  the workspace and home directory.
- **The tool set now follows the host OS**: `PowerShell` is registered only on
  Windows (or where `pwsh` is installed); macOS/Linux get Bash only. Previously
  the model saw a PowerShell tool on macOS and assumed the host was Windows.
- **`/model` no longer mangles model ids containing `/`** (e.g.
  `LiquidAI-dev/lfm2.5-2.6b:latest`, `anthropic/claude-3.5-sonnet`), which made
  local Ollama answer `400 invalid model name`.
- **Tool-call-only replies from small models are no longer dropped**: the stream
  loop counted only `content` chunks, so a `reasoning + tool_calls` response with
  empty content tripped the “Model returned no output” check and discarded the
  tool calls.
- **Answers are no longer misread as “plans”**: the plan-retry heuristic no longer
  fires on numbered lists, and content is rendered before any retry.
- **Literal `\n` in written files**: small models double-escape newlines; `Write`
  and `Edit` now repair that (`utils/text_escapes.py`).
- **Streaming display**: replaced the boxed panel (which parsed model output as
  rich markup and left overlapping artifacts) with a single-line status.

### Added
- OS-aware command guidance in the session context (macOS / Linux / Windows).
- `model_discovery.get_context_limit()`: the context budget uses the model's real
  window from the models.dev catalog (e.g. `glm-5.3` = 1M instead of the
  hard-coded 16k), so history is not compacted prematurely.
- Streaming errors now include the provider's response body.

## [0.1.41] - 2026-09-19

### Pivot to pi's design (Python implementation)
- **Rewrote the project around pi's design** — a minimal terminal coding agent
  (github.com/earendil-works/pi). The default surface now follows pi's: 9 tools, 23
  built-in commands, tree sessions, progressive-disclosure skills, and prompt
  templates.
- **Removed the feature-heavy subsystems** from the default path: supervisor,
  hyperauto, model assessment, explorer, scheduler, language sandboxes,
  extended-web auth, memory, insomnia, dual-model, adaptive router, anti-stall,
  bitter-lesson tracker, distilled templates, quality monitor, git store, plan
  mode, permissions, MCP, channels, HTTP server / web UI, cron, message bus, and
  the C translation.
- **Implemented pi's built-in commands** in `openlaoke/commands/pi_commands.py`:
  `new`, `name`, `session`, `tree`, `fork`, `clone`, `import`, `share`, `copy`,
  `changelog`, `hotkeys`, `trust`, `login`, `logout`, `reload`, `scoped-models`.
- **Added a pi-style prompt-template system** (`core/prompt_templates.py`) with
  `$1` / `$@` / `${1:-default}` / `${@:N:L}` argument expansion, wired to
  `/prompt` and to unknown `/name` commands.
- **Simplified local models**: removed the built-in GGUF runtime
  (`llama-cpp-python`, ModelScope download) and the `openlaoke model`
  subcommand. Local models now use the same formats as cloud providers —
  point `openai_compatible` (or `ollama` / `lm_studio`) at any
  OpenAI-compatible server such as Ollama. Local endpoints no longer require
  an API key.
- **Slimmed dependencies**: dropped `fastapi`, `uvicorn`, `websockets`, `jieba`,
  and `watchfiles`.
- **Result**: 286 files / 77,955 lines → 69 files / 19,349 lines; 7 runtime
  dependencies; 147 tests passing; `ruff` clean.

### Changed
- **Minimum Python is now 3.12** (was 3.11); `pyproject.toml`, the ruff target
  and the mypy target were updated accordingly.

### Fixed
- **Ollama streaming reasoning** — the OpenAI-compatible stream parser now reads
  `delta.reasoning` (Ollama thinking models) alongside `delta.reasoning_content`
  (DeepSeek). Thinking models previously produced an empty visible stream.
- **System prompt** — rewritten to list only the nine tools that actually exist;
  references to deleted tools (WebSearch, WebFetch, Agent) and the
  anti-AI-detection section were removed.
- **`pytest` collection** — `norecursedirs` now excludes `tests/artifacts`, whose
  model-generated `test_*.py` files broke collection.

### Docs
- Rewrote `README.md` and `README_CN.md` around pi's design, design
  philosophy, the pivot rationale, project history, and the speed/complexity
  trade-off.
- Added `THIRD_PARTY_NOTICES.md` (pi's MIT license and copyright).
- Removed the obsolete feature docs, architecture reports, test reports, and the
  C translation from `docs/`.
- Added `docs/benchmarks.md` / `docs/benchmarks_CN.md` and reproduction scripts
  in `scripts/` (provider formats, local-model capabilities, multilingual and
  concrete-task runs, inference speed).
- Corrected the provider documentation: OpenLaoKe speaks five native protocols
  (Anthropic Messages, OpenAI Chat Completions, Google `generateContent`,
  AWS Bedrock, Cohere), not "two formats".
- `tests/` is no longer tracked; the suite is kept local and git-ignored.

## [0.1.40] - 2026-08-24

### OpenCode-style Workflow Core
- **Conversation rewind** — `SnapshotStore.capture_conversation` persists per-turn conversation; `rewind_conversation` truncates live history (code / conversation / both scopes); rewinding to the first recorded turn clears the conversation
- **Session fork / branch** — `fork_session` inherits the parent's conversation and file snapshots; `Orchestrator.fork/branch/switch` register switchable sessions; forked sessions continue at the next turn index (never overwrite inherited records)
- **Command wiring** — `dispatch` now handles `Branch`, `Switch`, `SummarizeFrom`, `SummarizeUpTo`, `SetBypass`, `ForgetMemory`, `SaveDoc`
- **Plan mode unified on `PlanState`** — writer tools are blocked in the agent loop *before* the permission gate (Plan tool and read-only tools exempt); approval unblocks execution
- **Fixed: `SystemMessage.tool_use_id`** — tool results round-trip through serialization and rebuild as `role=tool` messages in the next turn
- **Fixed: `run_agent_loop` conversation capture** — assistant/tool messages are snapshotted at the loop boundary
- **`SnapshotStore` bounded cache** — LRU eviction (`max_cache_entries`, default 128) prevents unbounded memory growth in long sessions

### Dependency Slimming
- **Removed 6 unused runtime deps**: `anthropic` (REST via httpx), `mcp`, `aiofiles`, `tiktoken`, `jsonschema`, `setproctitle` — all verified zero code references
- **`watchfiles`** moved to the `dev` extra (uvicorn `--reload` only)
- Runtime dependencies: 18 → 11

### Test Coverage
- **+19 tests**: snapshot cache eviction, corrupt-line handling, unreadable paths, health checks, agent-loop edge cases (no API, shutdown, approval allow/deny), session round-trip
- `openlaoke/control/health.py` 37% → 88%; `snapshot/store.py` 90% → 94%; total (snapshot+control) 83% → 88%

### Thinking Display System
- **Thinking inline display** — model reasoning content shown inline (first 5 lines) with `Ctrl+G` to expand full content
- **`/thinking on|off|show`** — persistent toggle to control whether thinking auto-displays after each response
- **`thinking_enabled`** field on `AppState` — per-session thinking preference
- **Streaming thinking support** — `StreamEventType.REASONING` added; Ollama/cloud providers now stream reasoning content via `_parse_openai_stream_events`
- **Non-streaming thinking** — `_parse_openai_response` fills `AssistantMessage.thinking` from `reasoning_content` field
- **Multi-format extraction** — `<thinking>`, response tag detection, `<|thinking|>` support, plus `reasoning_content` field fallback

### Model Memory Cleanup
- **`BuiltinModelProvider.unload()`** — sets `_llm = None` + `gc.collect()` to free GPU/CPU memory
- **`atexit` handler** — model unloaded on normal Python exit
- **`SIGTERM/SIGINT` signal handler** — model unloaded on Ctrl+C or kill
- **`close()` in REPL `finally` block** — guaranteed cleanup on loop exit

### Code Quality
- **Dead code removed** (~2068 lines): `utils/compute.py` (754), `services/mcp.py` (600), `core/checkpoint.py` (261), `core/knowledge_base.py` (223), `extended_web/deepseek_client.py` duplicate (215), `utils/model_capabilities.py` (15)
- **Renamed**: `core/knowledge_base.py` → references updated to `EnhancedKnowledgeBase`
- **Merged**: ExtendedWeb `deepseek_client.py` duplicates consolidated into `clients/` version
- **Removed**: empty `components/` package
- **Fixed**: 4 locations silently swallowing exceptions → `logger.warning()` with context
- **Fixed**: `web_browser_tool.py` raised `RuntimeError` → returns `ToolResultBlock(is_error=True)`
- **Lint**: all ruff checks pass (previously 15+ errors across codebase)

### README Rewrite
- Removed all "built-in models" references — OpenLaoKe works with any model
- Removed legacy Qwen2.5 and outdated model references
- Streamlined to modern format with clean Quick Start, Tools, Slash Commands sections

### Model Tier System
- **`classify_model_tier()`** — heuristic-based tier classification replacing hardcoded `KNOWN_MODEL_TIERS` dict
- Size-based: >50B→TIER_2, >20B→TIER_3, >5B→TIER_4, ≤5B→TIER_5
- Provider-based: `claude-*`, `gpt-4o`, `o1` → TIER_1; `deepseek`, `llama-4` → TIER_2
- Updated `ModelAssessor`, `AtomicCommand`, `model_assessment/__init__.py` to use new function

### Model Names & Config
- Removed stale Qwen3:0.6b from config wizard preferred defaults
- `adaptive_router.py` default model: qwen2.5-coder:7b → llama3.2
- `small_model_optimizations.py`: removed qwen2.5 entries, added llama-4/gemma-3
- `intelligent_model_selector.py`: removed qwen2.5 references
- `local_model_manager.py`: `get_default_model()` returns None instead of hardcoded recommendation
- `_load_custom_models_registry()`: auto-cleans stale entries when model files are deleted

### WebFetch Error Messages
- Human-readable HTTP error explanations for 403/404/429/500/502/503

### Tests — 375 Pass, 0 Fail, 0.8s
- **`test_comprehensive.py`** — 181 tests covering all core modules, state, tools, hooks, compact, etc.
- **`test_core.py`** — deep tests for state, hook system, permissions, pruner, tracker, optimizer, supervisor
- **`test_tools.py`** — Bash, Read, Write, Edit, Glob, Grep with edge cases
- **`test_features.py`** — memory, bash classifier, commands, read tracker, context hygiene, integration
- **`test_new_modules.py`** — 74 tests for all new Round 2 modules (security, classifier, compound tools, router, trace, evidence, images, dependency graph)

### 新模块
- `utils/security.py` — path sanitization, credential redaction, ANSI stripping, tool arg sanitization
- `core/action_classifier.py` — regex-based message intent classification (clarify/action/greeting/praise/respond)
- `tools/compound_tools.py` — ReadAndPatch, FindAndRead, SearchAndRead (reduce sequential calls for small models)
- `core/adaptive_router.py` — 3-tier auto-promote/demote model routing based on failure rate
- `core/trace_recorder.py` — per-turn execution trace recording with regression test generation
- `core/evidence_store.py` — tracks attempted strategies and outcomes (what worked/failed)
- `core/message_images.py` — image path extraction, base64 encoding, vision API formatting
- `core/dependency_graph.py` — plan step file-dependency analysis and parallel execution groups

### Added - Research System

#### 溯源验证系统 (Provenance Tracking)
- `openlaoke/core/supervisor/provenance.py` - 完整的溯源追踪系统
  - `ProvenanceRecord` - 研究输出溯源记录，包含证据表、验证状态、来源统计
  - `VerificationStatus` - 验证状态枚举 (PASS / PASS_WITH_NOTES / BLOCKED / UNVERIFIED / INFERRED)
  - `SourceEntry` - 证据表条目，支持来源类型和置信度标记
  - `VerificationCheck` - 验证检查记录
  - 支持 Markdown 导出和加载 (`.provenance.md` 侧车文件)

#### Slug 命名与输出约定
- `openlaoke/core/supervisor/slug_utils.py` - 标准化文件命名
  - `generate_slug()` - 从主题生成短 slug (小写、连字符、过滤虚词、支持中文)
  - `get_output_paths()` - 获取标准输出路径 (plan/draft/cited/output/provenance)
  - `ensure_output_dirs()` - 创建所需目录结构
  - `validate_slug()` - slug 格式验证

#### 研究代理系统
- `openlaoke/core/multi_agent/research_agents.py` - 4 个专用研究子代理
  - `researcher` - 证据收集 (论文、Web、代码库)
  - `reviewer` - 模拟同行评审 (FATAL/MAJOR/MINOR 分级)
  - `writer` - 结构化草稿撰写
  - `verifier` - 引用添加和 URL 验证
  - 每个代理包含完整的 system_prompt 和工具列表

#### 工作流编排器
- `openlaoke/core/multi_agent/research_orchestrator.py` - 研究流程编排
  - `ResearchWorkflowOrchestrator` - 支持 deepresearch/lit/review 三种工作流
  - `WorkflowStep` - 带依赖关系的流程步骤
  - `WorkflowResult` - 工作流结果追踪
  - 自动 provenance 生成和验证状态计算

#### 研究命令
- `openlaoke/commands/research_commands.py` - 新增 4 个斜杠命令
  - `/deepresearch <topic>` - 深度研究，创建计划和溯源文件
  - `/lit <topic>` - 文献综述
  - `/review <artifact>` - 同行评审
  - `/outputs` - 浏览研究产出

#### 实验日志系统
- `openlaoke/core/supervisor/lab_notebook.py` - CHANGELOG 实验室笔记本
  - `LabNotebook` -  chronological 研究进度记录
  - `LabEntry` - 单条日志条目 (时间戳、slug、动作、状态、下一步)
  - 支持文件追加和加载

#### 上下文卫生管理
- `openlaoke/core/supervisor/context_hygiene.py` - 渐进式文件写入
  - `WriteBuffer` - 缓冲区和阈值刷新，避免内存累积
  - `extract_key_quotes()` - 从大内容中提取关键引用

#### 研究技能模板
- `openlaoke/skills/research/` - 4 个研究技能
  - `deep-research/SKILL.md` - 深度研究工作流
  - `literature-review/SKILL.md` - 文献综述
  - `peer-review/SKILL.md` - 同行评审
  - `source-comparison/SKILL.md` - 来源对比
- `openlaoke/core/skill_system.py` - 技能系统增强
  - 支持嵌套技能目录 (`dir/subdir/SKILL.md`)
  - 添加 `openlaoke/skills` 为默认技能目录

#### 类型系统增强
- `openlaoke/types/core_types.py` - `TaskState` 新增字段
  - `slug` - 任务 slug
  - `verification_status` - 验证状态
  - `provenance_file` - 溯源文件路径

#### 监督系统增强
- `openlaoke/core/supervisor/checker.py` - 新增检查类型
  - `provenance_check` - 溯源文件验证
  - `citation_check` - 引用格式和完整性验证
- `openlaoke/core/supervisor/supervisor.py` - 研究类需求自动提取
  - 识别 research/investigate/survey 关键词
  - 自动添加溯源、引用、证据表、验证状态需求

### Changed
- `openlaoke/core/multi_agent/__init__.py` - 导出研究代理和编排器
- `openlaoke/core/supervisor/__init__.py` - 导出所有新模块
- `openlaoke/commands/registry.py` - 注册研究命令

### Tests
- `tests/test_provenance.py` - 24 个测试 (溯源系统)
- `tests/test_slug_utils.py` - 15 个测试 (Slug 和路径)
- `tests/test_lab_notebook.py` - 10 个测试 (实验日志)
- `tests/test_context_hygiene.py` - 8 个测试 (上下文卫生)
- `tests/test_research_agents.py` - 14 个测试 (研究代理)
- `tests/test_research_orchestrator.py` - 15 个测试 (工作流编排)
- `tests/test_research_commands.py` - 10 个测试 (研究命令)
- 总计新增 **96 个测试**，全部通过
