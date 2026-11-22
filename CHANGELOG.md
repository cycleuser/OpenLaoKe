# Changelog

All notable changes to OpenLaoKe will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.46] - 2026-11-21

### Added
- **Arrow-key model picker** (`core/prompt_input.py`): `Ctrl+P` opens a
  full-screen picker with `↑`/`↓`/PageUp/PageDown/Home/End, Enter to confirm,
  Esc to cancel, and type-to-filter. The active model is preselected and
  marked `*`; the list scrolls instead of dumping every model into the
  scrollback.
- **`/models` alias and probe/prune** (`commands/base.py`): `/models` works
  like `/model`. `/model probe` rechecks local servers; `/model prune` removes
  unreachable local providers in one step.
- **Custom and preset providers persist** (`utils/config.py`): provider type,
  model list, and local flag are saved and reloaded. `/model add
  cycleuser-llm` now keeps the `halogen` models after a restart.
- **Live model names and labels** (`core/model_discovery.py`,
  `core/prompt_input.py`): the picker refreshes each ready provider's
  `/models` endpoint, shows the provider's display name next to the id, and
  treats the live endpoint as authoritative instead of unioning stale
  models.dev entries. DeepSeek now shows `deepseek-flash` (served by
  DeepSeek-V4.1-Flash-1017) and `deepseek-v4-pro`; Ollama Cloud shows
  `deepseek-v4.1-flash:1017`. A generic `openai_compatible` entry that points
  at the same base URL as a typed provider is hidden.
- **LFM3 local-model comparison** (`bench/lfm3_compare.py`,
  `docs/lfm3-local-models.md`): LFM3-1.7B and LFM3-Omni-2B, each as GGUF
  (llama.cpp) and MLX 8bit (MLX-VLM), on speed, six text checks, tool calls,
  image input and one OpenLaoKe agent task. `bench/qwen_compare.py` runs the
  same text and agent checks against Qwen3.5-2B (GGUF Q4 and MLX 4bit).

### Fixed
- **Dead local providers are detected at startup** (`types/providers.py`,
  `core/repl.py`): Ollama and LM Studio are probed concurrently with a 0.75s
  timeout and no proxy. Unreachable ones are hidden from the picker and shown
  in a separate "unreachable local providers" section with a removal hint.
  A 30-second cache avoids repeated probes; `/model probe` refreshes it.
- **`/model` shows the active model**, not the provider default, and no longer
  lists uninstalled local servers among the usable providers.
- **OpenAI-compatible servers that return `tool_calls: null`** are accepted
  (`core/multi_provider_api.py`): MLX-VLM emits `null` for ordinary text
  replies; parsing now treats it as an empty list instead of raising
  `'NoneType' object is not iterable`.

## [0.1.45] - 2026-11-21

### Changed
- **Reasoning effort is configurable and defaults to low** (`utils/config.py`,
  `core/multi_provider_api.py`, `entrypoints/cli.py`): `reasoning_effort`
  (and `--reasoning-effort`) sets how hard a reasoning model thinks. `low`
  matches what Jcode and pi use for coding turns and cuts latency; set `""`
  to leave it to the provider. Local providers still skip thinking.
- **Prompt folds in the other agents' strengths** (`core/cache_guard.py`):
  read AGENTS.md/README and follow project conventions, batch independent
  reads in one turn, verify once, and stop as soon as the task is done.
- **Focused tool profile for headless runs** (`tools/register.py`,
  `entrypoints/cli.py`): `openlaoke "<prompt>"` now sends only the nine core
  coding tools (Read, Write, Edit, Grep, Glob, ListDirectory, ApplyPatch,
  InvokeSkill, shell) instead of all 23. Tool-schema prompt tokens drop by
  roughly 65% per model call; `--all-tools` restores the full surface.
- **The headless loop matches the REPL's reliability** (`core/engine.py`):
  tool-name/argument repair, an identical-call loop guard, and parallel
  dispatch of read-only tool batches.
- **Clearer base system prompt** (`core/cache_guard.py`): explicit
  act-inspect-edit-verify workflow, evidence-based completion, and relative
  paths.

### Fixed
- **Text tool calls are recovered** (`core/text_tool_calls.py`,
  `core/engine.py`): when a local runtime returns Qwen-style
  `<tool_call><function=...>` XML as plain assistant text, OpenLaoKe now parses
  it back into real tool calls and executes them. The XML is removed from the
  visible answer. This keeps 2B models useful when the server's parser misses
  their format.
- **Local endpoints are free** (`core/multi_provider_api.py`): cost
  calculation now returns zero when the active base URL is localhost, instead
  of charging an unknown local model at the default cloud price.
- **Small models keep files in the workspace** (`core/cache_guard.py`): the
  base prompt now says to use paths relative to the working directory and not
  `/tmp`. A local 2B model otherwise wrote `fib.py` to `/tmp` and then
  reported success.
- **Cloudflare-fronted gateways** (`core/multi_provider_api.py`): send a
  browser-compatible `User-Agent` and `Accept: application/json`; plain
  library User-Agents were answered with a 403 challenge page even for valid
  keys. Override with `OPENLAOKE_HTTP_USER_AGENT`.
- **Edit argument aliases** (`core/small_model_optimizations.py`):
  `old_string`/`new_string` now map to the tool's real `old_text`/`new_text`
  schema instead of the reverse.
- **Truncated model output** (`core/engine.py`): an empty answer with
  `finish_reason=length` is reported as an error instead of a silent success.
- **Reasoning-model fallback** (`core/multi_provider_api.py`): read
  `reasoning_content` as well as `reasoning`/`thinking`.

### Added
- **Document tool-use benchmark** (`bench/agent_compare.py`,
  `docs/benchmarks.md`): five seeded DOCX/XLSX/PDF/CSV tasks with hidden
  filesystem checks, plus harness and model matrices. All four harnesses pass
  5/5 on `halogen`; Ollama Cloud `glm-5.3` is the fastest model; a local
  Qwen3.5-2B completes 0/5 document tasks despite calling tools.
- **Switchable harness modes** (`core/harness_modes.py`, `/mode`, `--mode`):
  `balanced` (default), `pi`, `jcode`, `opencode`, and `deep` bundle the reference
  agents' temperaments: reasoning effort, step budget, tool profile, and
  system-prompt directives. `/mode` switches mid-session (applies from the next
  turn and invalidates the cached prompt); `--mode` selects one for a single
  run; `deep` uses high reasoning for hard debugging and design work; aliases
  `fast`, `robust`, `thorough`, and `max` are accepted. The same knobs
  feed `EnginePolicy` in headless, sub-agent, and bot loops, so the mode is not
  cosmetic.
- **Provider experience matches Jcode** (`core/provider_presets.py`,
  `commands/base.py`, `core/config_wizard.py`): twelve curated presets
  (including `llm.cycleuser.com` and `ai.cycleuser.com`) replace the
  twenty-five-provider wall. Keys are read from environment variables, never
  embedded. `/model` lists only providers with a usable credential (local
  servers show as `local`), `/model add` offers the preset picker or an explicit
  `name url [key] [model]`, and `/model rm <name>` removes one.
- **Four-agent benchmark** (`bench/agent_compare.py`, `bench/ua_proxy.py`):
  runs OpenLaoKe, Jcode, OpenCode and pi on the same tasks and model in
  isolated sandboxes, verifies on the filesystem, retries infrastructure
  failures, and emits a comparison JSON. `ua_proxy.py` injects the browser
  headers Cloudflare-fronted gateways require. The API key is read from
  `OPENLAOKE_BENCH_API_KEY`.
- **Bot mode** (`core/bot_mode.py`, `/bot`, optional `MessageAgent` tool): a roster of
  named agents, each with a title, role, optional model/persona/skills and one canonical
  chat under `~/.openlaoke/bots/`. `/bot use <name>` routes plain input to that bot;
  `/bot room new <room> <bot> <bot>` opens a bounded shared conversation (three serial
  rounds, ten replies, one turn per member per message, `@name` handoffs, `@user` stops
  the room, `[SILENT]` skips). Bots message each other through a JSON inbox drained after
  each turn; `MessageAgent(wait=true)` is refused while the target is mid-turn instead of
  deadlocking. Routines are ordinary scheduler entries named `[bot:<name>] ...`, and
  `openlaoke --bot <name> "..."` / `--room <room> "..."` run a single turn outside the
  REPL. `--readonly` bots get a read/search/web tool allow-list.
- **Generated tool and command reference** (`docs/tool-reference.md`,
  `scripts/dump_tool_reference.py`): built from the registry and the command list, with
  `--check` exiting non-zero when the file is stale, and a test that keeps it honest.
- **Whitespace-tolerant `Edit`** (`utils/fuzzy.py`): when the exact text is not
  found, the tool retries ignoring trailing whitespace, then comparing with runs of
  whitespace collapsed; the replacement is applied at the matched span and the result
  says which mode was used. `replace_all` refuses a fuzzy match, since "replace every
  occurrence of something that only roughly matched" is not a safe instruction.
- **`/sleep` (hibernate)**: releases the memory index, cache readings, swarm board and
  task handles and runs a collection pass, refusing while swarm workers are running.
  Each store rebuilds itself from disk on next use, so nothing is lost.
- **`Swarm` tool** (`core/swarm.py`): up to six workers on separate lanes, each a
  sub-agent with its own context. `start` returns immediately with worker ids,
  `await` collects them with a timeout, `status` shows state and results, `note` and
  `messages` are a shared board, `cancel` stops the rest. Every write made by a worker
  is attributed to that worker through a context variable and recorded in a touch
  ledger, so "two lanes edited the same file" is visible instead of inferred. The
  final report is bounded and split evenly between lanes.
- **Shared agent loop** (`core/engine.py`): one implementation of the request /
  tool-call / result cycle, used now by the sub-agent runner and the non-interactive
  CLI. It adds what the two small loops were missing - argument validation, a tool
  allow-list, a permission callback, an abort signal and a state-save hook - and the
  REPL uses its `assistant_turn` / `tool_result_message` helpers so the message shapes
  cannot drift apart again.

### Fixed
- Sub-agent tool results were sent as `{"role": "tool_result"}`, an internal shape the
  provider adapters had to special-case; they now use the canonical
  `{"role": "tool", "tool_call_id": ...}` like the interactive loop.
- **`Browser` tool** (optional extension, off by default): open a page, read its
  rendered text, list links, or run JavaScript. It only registers when both
  `enable_browser` is set and `selenium` imports; a missing dependency is reported
  with a pointer to `WebFetch` instead of a tool that fails on every call.
- **`Schedule` tool and `/schedule`** (`core/scheduler.py`): local entries in three
  forms only - `every 30m`, `daily 09:00`, and a one-shot `2026-11-09T08:30` - that
  either queue a prompt for the next turn or run a shell command in the background.
  The list is a JSON file that survives restarts; the tick loop is off unless
  `enable_scheduler` is set, and nothing fires while the session is closed.
- **`Panel` tool** (`core/panel_render.py`): renders markdown to one self-contained
  HTML file with inline CSS - headings, lists, fenced code, inline code,
  bold/italic, links, quotes and rules. Raw HTML in the input is escaped and
  `javascript:` links are not emitted; the file can be opened immediately.
- **`Open` tool**: hands an http(s) URL or a workspace path to the platform opener;
  other schemes and paths outside the workspace are refused by name.
- **`OpenLaoKeDocs` tool**: lists, searches and reads this repository's own docs
  (`docs/` plus the root README/CHANGELOG/AGENTS), splitting markdown by heading and
  ranking sections with the shared BM25 scorer, so "how does the context budget work"
  is answered from the actual document.
- **`Compile` tool**: builds a document locally with a whitelist - `latexmk`/`pdflatex`,
  `pandoc`, `typst`, or `py_compile` - in the source directory with a timeout, reporting
  the files it produced and naming a missing binary instead of failing obscurely.
- **`/skill info <name>` and `/skill off <name>`**: show a skill's body, or deactivate
  one without clearing the rest.
- **`CodeMode` tool and sandbox** (`core/code_sandbox.py`): runs a Python script over
  the workspace so "parse these forty files and print five lines" is one call instead
  of forty. Each run is a fresh `python -I -B` process with a scrubbed environment, a
  guarded `open` that refuses paths outside the workspace, an import hook that refuses
  process/network/FFI modules, `os.system` neutralised, CPU and address-space rlimits,
  a wall-clock timeout that kills the process, and capped output. Helpers:
  `read/write/append/ls/exists/glob/walk/grep`. The docstring says plainly that this
  stops accidents, not a determined attacker, since the guards run inside the child.
- **`/stats` dashboard**: one screen with tokens in/out, cache hit rate, estimated
  cost, tool-call counts, edit totals, task-list state, running background jobs,
  memory size and the recent cache hit rate. Tool calls are now counted per name and
  persisted with the session.
- **`scripts/productivity_report.py`**: Markdown report over the saved sessions -
  activity per day, which directories saw the work, which tools carried it, and token
  totals; no model calls, and sessions without reported usage show zero rather than a
  guess.
- **MCP support** (`core/mcp_client.py`, `core/mcp_runtime.py`, `/mcp`): servers
  configured under `mcp_servers` are started over stdio at session start, their
  `tools/list` becomes local tools named `mcp__server__tool`, and calls go through
  `tools/call`. Server tools get the same `intent` field and the same result ledger as
  built-in ones. A server that cannot start is reported in `/mcp` and skipped instead
  of blocking the session.
- **Background task notices**: when a job started with `Bash(background=...)` finishes,
  the next turn receives one line naming the task and its exit code, so the model does
  not have to remember to poll. Each task is announced once.
- **`WebSearch` tool**: queries the DuckDuckGo HTML endpoint (no API key, no JS),
  unwraps its redirect links, and returns titles, URLs and snippets; pair it with
  `WebFetch` to read the result that matters. A challenge page or a markup change is
  reported as "no results parsed" rather than as invented hits.
- **`SessionSearch`, `ConversationSearch`, `/search` and `/sessions`**: BM25 over the
  saved sessions on disk (filterable by age, directory and role) and over the live
  conversation, including messages compaction has removed from view. Tool results are
  truncated before indexing so one large read cannot outrank a discussion. The shared
  tokeniser now also splits mixed alphanumeric runs, so `3000` matches `3000ms`.
- **`Memory` tool and `/memory`**: durable project notes in a JSON file under
  `~/.openlaoke/memory/`, one store per working directory, retrieved with BM25 over
  words plus CJK character bigrams. Actions are remember, recall, search, list,
  forget, tag, link, related and stats; identical text is stored once. The system
  prompt gets a short index of note ids and previews only, so the fixed cost does not
  grow with what has been remembered.
- **`ApplyPatch` tool**: applies a multi-file patch given either as the
  `*** Begin Patch` envelope (`*** Add File` / `*** Update File` with `@@` hunks /
  `*** Delete File`) or as a unified diff. Every hunk is matched in memory before
  anything is written, so a patch that cannot apply completely changes nothing; paths
  outside the workspace, adding an existing file and updating a missing one are all
  refused. Patches feed the same edit counters as `Write` and `Edit`.
- **`Batch` tool** (off by default): 1-10 independent calls in one turn, run
  concurrently. Destructive tools are refused because a batch bypasses the
  interactive permission prompt, nesting a batch is refused, and `/batch on|off`
  toggles it for the session (`enable_batch` in the config file).
- **Background jobs** (`core/task.py`, `Bg` tool): a `Bash` command still running
  after `auto_background_timeout_ms` (default 3000) is handed to the background and
  its task id is returned, so a slow build no longer blocks the turn; `timeout` stays
  a hard deadline that kills the process. Output is streamed to a per-task log file
  instead of an in-memory buffer, `Bg` reads it by `tail`, `output` (with a character
  offset to resume), `wait`, `watch` or cancels it, and `background=true` starts a
  command there directly.
- **Edit accounting** (`core/edit_stats.py`, `/edits`): `Write` and `Edit` record
  created versus modified files and the true lines added and removed (sequence
  match, not a line-total subtraction), persisted with the session.
- **Session environment snapshots** (`AppState.snapshot_env`): each job captures
  the environment once at spawn, so changing a session variable mid-run cannot
  change the meaning of a command already in flight.
- **Turn and tool hook points** (`core/hook_system.py`): `turn_start`, `turn_end`,
  `tool_gate` and `tool_feedback` join the existing extension points, and the names
  jcode uses (`pre_tool`, `post_tool`, `pre_tool_transform`, `post_tool_feedback`)
  register as aliases of them. `tool_gate` runs after argument rewriting and before
  the permission check, so a plugin can veto a call the user is never asked about;
  `tool_feedback` text is queued for the model instead of being injected into the
  tool result. Every hook may carry `timeout_ms`: async hooks are bounded by
  `asyncio.wait_for`, sync ones are measured, and overruns are counted in the stats.
- **Prompt-cache monitor** (`core/cache_monitor.py`, `/cache`): fingerprints the
  cacheable prefix (model, system prompt, tool names, all but the newest message) so
  a change that will invalidate the provider cache is visible, and reads the
  provider's cache counters back to report hit rate, tokens served from cache, and
  runs of turns without a cache read.
- **Startup cost gate** (`scripts/bench_startup.py`): imports the entry module in a
  cold interpreter, reports import time, peak RSS and the largest imported modules,
  and exits non-zero over budget.
- **`WebFetch` tool**: reads a URL through httpx (already a dependency) and returns the
  page as text with scripts, styles and markup removed; the title is kept, output is
  capped by `max_chars`, and a repeat of the same page collapses to a ledger pointer.
- **Four-tier command risk** (`utils/permissions/command_risk.py`): shell lines are
  classified offline by blast radius - `safe`, `low` (destructive but bounded to the
  working directory: runs and is recorded in `risk_events`), `confirm` (target comes
  from a glob, variable, or reaches outside the directory: the call must come back with
  a `justification`), and `catastrophic` (filesystem root, device nodes, credential
  stores, `sudo`: refused, and a justification does not unlock it).
- **Session context budget** (`core/context_budget.py`, `/context`): the effective
  budget is the smaller of the model window and a per-session cap, the cap may
  raise or lower the global `context_cap_tokens` but never exceeds the window, and
  the provider's reported usage is preferred over estimation. `/context 24k` sets a
  cap for this session, `/context clear` removes it.
- **Result ledger** (`core/result_ledger.py`): a tool result the model has already
  been shown collapses to a pointer naming the earlier call and the token count
  saved; a result above 1500 tokens is returned as head+tail with its cost stated,
  and only sent in full when the call repeats with `accept_large_output=true`.
- **Structure-aware search**: `Grep` now annotates each hit with the class or
  function containing it and its line range, and gained `mode='find'` (match file
  names) and `mode='outline'` (list a file's definitions), plus `paths_only` and
  `max_regions` for cheap passes.
- **`intent` on every tool**: each call carries a short label for why it was made,
  shown at the end of the tool line.
- **`Todo` tool and `/todos`**: named tasks with phases, lanes, `after`
  prerequisites, `blocked_reason` and required `evidence`. A task cannot be
  recorded done without saying what proved it, and while tasks stay open the loop
  sends at most three continuation prompts per unchanged list.
- `--max-steps` is honoured (it was written to state but never read).

### Fixed
- Bash spawns with `start_new_session` only on POSIX; the keyword is unsupported on
  Windows and would have raised on a git-bash setup.
- `build_compact_prompt` raised `ModuleNotFoundError` for any call with user input
  (two imports pointed at modules that do not exist); `hook_system.v2` imported a
  missing module the first time it was touched.
- `AppState._persist` wrote `guard_state` and `compact_state` from attributes that
  do not exist, so both were silently dropped on every save.
- Token estimation counted CJK text as `len()//4`, undercounting Chinese by roughly
  a factor of two to three; eight call sites in the pruner now use a CJK-aware
  estimator.
- `mypy openlaoke` reports no errors (was 6), and `ruff format --check` is clean.

## [0.1.44] - 2026-09-19

### Changed
- Re-release from the same source as 0.1.43; no functional changes.

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
