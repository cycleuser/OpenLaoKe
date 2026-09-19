# OpenLaoKe

> A terminal coding agent that follows [pi](https://github.com/earendil-works/pi)'s design — minimal, fast, extensible, implemented in Python.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: GPLv3](https://img.shields.io/badge/license-GPLv3-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

## What OpenLaoKe is now

OpenLaoKe **follows pi's design, implemented in Python**. It keeps pi's core idea — a tiny, opinionated agent loop that you extend yourself — and drops almost everything else.

- **9 tools**, matching pi's surface: `Read`, `Write`, `Edit`, `Bash`, `Grep`, `Glob`, `ListDirectory`, `PowerShell`, plus `InvokeSkill` for on-demand skills.
- **pi's 23 built-in commands**, plus prompt templates and skills.
- **Session tree with branch / fork / clone / rewind**, backed by append-only files.
- **Prompt templates** (`/name` and `/prompt <name>`), with `$1`, `$@`, `${1:-default}`, `${@:N:L}`.
- **API keys or local endpoints** — OpenAI and Anthropic (Claude) formats, plus any OpenAI-compatible server (Ollama, LM Studio, …).
- ~19k lines of Python. No MCP, no sub-agents, no plan mode, no permission popups, no background bash.

### Tools

| Tool | Purpose |
|------|---------|
| `Read` | Read files (text, images, PDFs) |
| `Write` | Create or overwrite files |
| `Edit` | Targeted string replacement edits |
| `Bash` | Run shell commands (streaming) |
| `Grep` | Regex search across files |
| `Glob` | Find files by pattern |
| `ListDirectory` | List directory contents |
| `PowerShell` | Windows command execution |
| `InvokeSkill` | Load an installed skill at runtime |

### Slash commands

pi's built-in command set is implemented one-to-one:

`/new` `/name` `/session` `/tree` `/fork` `/clone` `/compact` `/resume` `/export` `/import` `/copy` `/share` `/changelog` `/hotkeys` `/scoped-models` `/trust` `/login` `/logout` `/reload` `/model` `/thinking` `/settings` `/quit`

Plus OpenLaoKe additions that fit the same philosophy: `/prompt` (expand a prompt template), `/skill` (list or activate a skill), `/theme`, `/help`.

## Design philosophy

OpenLaoKe follows pi deliberately, and the philosophy is the point:

**1. A minimal core, extended outward.** The default tool set is small and stable. Capabilities arrive through skills, prompt templates, hooks, and your own code — not through a growing pile of built-in features. A small core is easier to reason about, faster to start, and cheaper to run.

**2. Speed is a function of the fixed context baseline.** Every request re-sends the system prompt, tool schemas, and skill metadata. That fixed cost, multiplied by every model turn, is the dominant latency and cost term. Feature-rich harnesses pay it on every call. Keeping the baseline small is a design decision, not an optimization afterthought — see *Speed and complexity* below.

**3. Progressive disclosure.** Skill bodies are not in context until invoked. Only names and short descriptions travel with the prompt; the full instructions load when the model actually needs them.

**4. Sessions are trees, not lines.** Every session is an append-only log with parent links, so you can fork, clone, or rewind in place without losing history.

**5. Opinionated omissions.** pi says *No MCP, no sub-agents, no permission popups, no plan mode, no built-in to-dos, no background bash.* OpenLaoKe inherits this list. These are not missing features; they are features you build when you actually want them.

**6. Local-first, zero-cost capable.** Point OpenLaoKe at a model running on your own machine — an OpenAI-compatible endpoint is a first-class option, not a fallback.

## Why we pivoted

This section is honest project history, because the pivot is the interesting part.

OpenLaoKe was not originally built around pi's design. It began in April 2026 as a feature-rich, OpenCode-style assistant: 30+ tools, MCP, sub-agents, a supervisor, a plan mode, permissions, memory, an anti-AI-detection layer, dual-model collaboration, a web UI, a FastAPI server, and more. It grew to roughly **78,000 lines** and 286 modules.

Then we measured. Running the same model on the same task across harnesses showed that the *fixed* per-request overhead — system prompt plus tool schemas — dominated everything. In one controlled comparison, a minimal harness sent ~1.5k tokens per request at the baseline; a feature-rich one sent ~7.3k. Adding skills cost roughly 210 tokens each on both sides, identically, because both used the same Agent Skills standard. The conclusion was uncomfortable but clear:

> Most of the "power" of a feature-rich harness is a constant tax paid on every single turn, and it buys you features you often do not use.

So we made a decision: **keep the engineering we were proud of, but adopt the design that produces the numbers.** OpenLaoKe now follows pi's design, implemented in Python. The result:

| | Before | After |
|---|---:|---:|
| Python files | 286 | **69** |
| Lines of code | 77,955 | **19,349** |
| Runtime deps | 11 | **7** |
| Tests | — | **147 passing** |
| Built-in commands | 40+ | **23 (pi parity)** |

The removed code is preserved in the git history. Nothing was lost; it was moved out of the default path.

## A short history

The commit log tells the story in four phases: **grow → specialize → consolidate → simplify.**

**Phase 1 — Build the engine (April 2026).** The initial commit landed a provider-agnostic agent loop. Very quickly it grew model-side machinery: CPU/GPU hybrid inference, intelligent model selection, batch operations, dual-model collaboration, model preloading, atomic generation, and HyperAuto (an autonomous self-improvement mode).

**Phase 2 — Reach the edges (April–May 2026).** Browser-based provider authentication (Chrome/Firefox), a `Ctrl+P` model picker, and — importantly — local GGUF models via llama-cpp-python, making zero-API-cost operation real. Memory tools and a growing tool set followed.

**Phase 3 — Consolidate (May–August 2026).** The pieces matured: a thinking display system, a cache-aware prompt engine with a byte-stable prefix, the `InvokeSkill` meta-tool (keeping the tool schema stable no matter how many skills are installed), mid-session display-language switching, and an OpenCode-style workflow core with rewind / fork / branch and plan-mode gating. We added architecture diagrams and public acknowledgements to the projects whose patterns we borrowed. Dependencies were trimmed once already.

**Phase 4 — Simplify (September 2026).** The pivot to pi's design. After the benchmark above, the whole feature surface was re-examined against a single question: *does pi have this?* If not, it left the default path. The repository went from 78k to 19k lines, the tool set from 30+ to 9, and the command set to pi's 23. The codebase now reads like the design it follows: small, legible, and fast.

## Speed and complexity

Speed here means wall-clock time from hitting Enter to getting an answer, and it is shaped almost entirely by three things.

**The fixed context baseline.** Every turn re-sends the system prompt, tool schemas, and skill metadata. A minimal harness sits around 1.5k tokens; a feature-heavy one can pass 7k before the user's message is even counted. On a multi-turn task this multiplies by the number of turns. OpenLaoKe's default path is deliberately on the small side.

**Per-skill cost.** Skills are metadata-only until invoked. In measurement, each skill costs roughly 210 tokens of fixed context regardless of the harness, because both implement the Agent Skills standard. The lesson: skill count scales cost linearly, so install what you use.

**Turn count and tool round-trips.** Fewer, sharper tools mean fewer round-trips. Nine tools that the model understands well beat thirty tools it has to disambiguate.

Complexity is the other half of the trade. A 19k-line codebase with a flat module layout is something you can hold in your head, audit for safety, and extend without fear. That legibility is worth more, in our view, than a long feature list — and it is the reason the pivot happened.

## Sessions

`~/.openlaoke/sessions/` holds append-only session JSON; `~/.openlaoke/snapshot/` (via `SnapshotStore`) records per-turn file and conversation state. That enables:

- `/tree` — list recorded turns and rewind to any of them (code + conversation)
- `/fork [turn]` — branch at a turn, inheriting that point's history
- `/clone` — duplicate the session at the current position
- `/compact` — prune context with a pure-algorithm fast pruner (no LLM call)

## Skills

Skills follow the [Agent Skills](https://agentskills.io) standard: a directory with a `SKILL.md` containing YAML frontmatter and Markdown instructions.

```text
~/.openlaoke/skills/<name>/SKILL.md   # project: .openlaoke/skills/<name>/SKILL.md
```

Only the name and description enter the system prompt; the body is read when `InvokeSkill` is called. `/skill` lists what is installed and activates one.

## Prompt templates

Reusable Markdown prompts, pi-style. Drop a file in `~/.openlaoke/prompts/review.md` and invoke it:

```markdown
---
description: Review staged changes
argument-hint: "<path>"
---
Review the staged changes. Focus on $1, then ${2:-correctness}.
```

```text
/review src/app.py        # or: /prompt review src/app.py
```

Supported argument syntax: `$1`, `$2`, … positional; `$@` / `$ARGUMENTS` for all; `${1:-default}` and `${@:-default}` for defaults; `${@:N}` and `${@:N:L}` for slicing.

## Quick start

```bash
pip install openlaoke
openlaoke
```

Requires Python 3.11+.

### API keys

Set a key and go:

```bash
export OPENAI_API_KEY=sk-...         # OpenAI format
export ANTHROPIC_API_KEY=sk-ant-...  # Claude format
openlaoke --provider openai --model gpt-4o
```

### Local models

OpenLaoKe speaks the OpenAI and Anthropic formats. For a local model, run any OpenAI-compatible server and point OpenLaoKe at it — how you run that server is up to you. With [Ollama](https://ollama.com):

```bash
ollama serve
ollama pull llama3.2

openlaoke --provider openai_compatible \
  --base-url http://127.0.0.1:11434/v1 \
  --api-key not-needed \
  --model llama3.2
```

Local endpoints need no real API key. LM Studio (port 1234), vLLM, and any other OpenAI-compatible server work the same way.

### Providers

Cloud: OpenAI, Anthropic (Claude), Azure OpenAI, Google, Google Vertex, AWS Bedrock, xAI, Mistral, Groq, Cerebras, Cohere, DeepInfra, Together AI, Perplexity, OpenRouter, GitHub Copilot, MiniMax, Aliyun Coding Plan. Free/local: OpenCode Zen, and any OpenAI-compatible endpoint (Ollama, LM Studio, vLLM, …).

## Configuration

`~/.openlaoke/config.json`:

```json
{
  "providers": {
    "active_provider": "ollama",
    "active_model": "llama3.2",
    "providers": {
      "ollama": { "base_url": "http://localhost:11434/v1", "default_model": "llama3.2", "enabled": true },
      "openai": { "api_key": "sk-...", "default_model": "gpt-4o", "enabled": false }
    }
  },
  "proxy_mode": "none",
  "max_tokens": 8192,
  "theme": "dark"
}
```

### Environment variables

`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, `MINIMAX_API_KEY`, `XAI_API_KEY`, `MISTRAL_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `GITHUB_TOKEN`, `OPENLAOKE_MODEL`, `HTTP_PROXY` / `HTTPS_PROXY`.

## Architecture

```text
openlaoke/
├── entrypoints/cli.py     # argparse CLI + config wizard entry
├── core/
│   ├── repl.py            # interactive loop, streaming, tool dispatch
│   ├── agent_runner.py    # provider-agnostic agent turn
│   ├── multi_provider_api.py
│   ├── sessions.py        # session persistence
│   ├── snapshot/          # per-turn file + conversation snapshots
│   ├── compact/           # fast pruner + summarizer
│   ├── skill_system.py    # Agent Skills loader
│   ├── prompt_templates.py
│   ├── hook_system.py     # extension points
│   └── tool.py            # Tool / ToolRegistry
├── tools/                 # read, write, edit, bash, grep, glob, ls, powershell, invoke_skill
├── commands/              # pi command set + prompt/skill commands
├── types/                 # core types, providers, hooks
└── utils/                 # config, theme, diff, path safety
```

## Development

```bash
pip install -e ".[dev]"
ruff check . && ruff format .
pytest
```

147 tests cover the pi-compatible commands, prompt templates, sessions, snapshots, tools, diffing, and i18n.

## Benchmarks

Provider-format verification, local-model capability checks, and a two-harness
(OpenLaoKe vs pi) multilingual comparison across six local models and ten
languages are documented in [`docs/benchmarks.md`](docs/benchmarks.md)
(English) and [`docs/benchmarks_CN.md`](docs/benchmarks_CN.md) (中文).
Reproduction scripts live in [`scripts/`](scripts).

## Acknowledgements

OpenLaoKe follows the design of **[pi](https://github.com/earendil-works/pi)** by Mario Zechner, implemented in Python. pi is MIT-licensed; OpenLaoKe is GPLv3.

Earlier iterations also drew on patterns from:

- **[nanobot](https://github.com/HKUDS/nanobot)** — event-driven agent loop, AutoCompact
- **[smallcode](https://github.com/Doorman11991/smallcode)** — tool-call parsing, read-before-write guard
- **[OpenCode](https://github.com/opencode-ai/opencode)** — full-screen TUI, session fork/branch model

## License

GPLv3. pi is MIT, which is compatible with GPLv3; its copyright notice is retained in `THIRD_PARTY_NOTICES.md`.
