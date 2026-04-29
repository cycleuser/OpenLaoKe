"""Cross-project lessons learned from analyzing 16 AI coding assistant projects.

Projects analyzed:
- kwcode, kaiwu, hermes-agent, hermes-agent-self-evolution, hermes-web-ui
- OpenHarness, rlm, rlm-minimal, llm_wiki, Viral_Writer_Skill, AutoCLI
- FreeAskInternet, VibeGPS, learn-claude-code, awesome-hermes-agent

Each lesson follows The Bitter Lesson principle:
"Methods that leverage computation and learning scale better than methods
that rely on human-engineered knowledge."
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProjectLesson:
    """A lesson learned from analyzing a specific project's approach."""

    source_project: str
    category: str  # "small_model", "architecture", "context", "tools", "prompt", "ui"
    lesson: str
    what_works: str
    what_fails: str
    bitter_lesson_alignment: bool  # Does this align with The Bitter Lesson?
    priority: str = "high"  # high, medium, low
    implementation_status: str = "pending"  # pending, done, skipped


CROSS_PROJECT_LESSONS: list[ProjectLesson] = [
    ProjectLesson(
        source_project="rlm, rlm-minimal",
        category="small_model",
        lesson="REPL-based context offloading beats stuffing everything into context window",
        what_works="Model writes Python code to explore data instead of reading all files into context. Recursive sub-calls let small models delegate.",
        what_fails="Loading entire codebase into context. Small models lose track when context exceeds 4K tokens.",
        bitter_lesson_alignment=True,
        priority="high",
        implementation_status="pending",
    ),
    ProjectLesson(
        source_project="hermes-agent",
        category="tools",
        lesson="Tool argument type coercion is the #1 fix for small model failures",
        what_works="Automatically coerce '42' -> 42, 'true' -> true before tool execution. Schema sanitization for llama.cpp compatibility.",
        what_fails="Rejecting tool calls because model returned string instead of int. Wasting iterations on type errors.",
        bitter_lesson_alignment=True,
        priority="high",
        implementation_status="done",
    ),
    ProjectLesson(
        source_project="learn-claude-code",
        category="context",
        lesson="Three-layer context compression (micro/auto/compact) enables infinite sessions",
        what_works="Micro: silently shrink tool results every turn. Auto: summarize when threshold hit. Compact: model-triggered.",
        what_fails="Naive truncation loses critical context. LLM-only summarization is slow and expensive.",
        bitter_lesson_alignment=True,
        priority="high",
        implementation_status="done",
    ),
    ProjectLesson(
        source_project="kwcode",
        category="small_model",
        lesson="Deterministic pipeline > LLM-decided next step for small models",
        what_works="Fixed pipeline: locate -> generate -> verify. LLM never decides the next step. Retry with reflection.",
        what_fails="Letting small models decide their own strategy leads to infinite loops and wandering.",
        bitter_lesson_alignment=True,
        priority="high",
        implementation_status="done",
    ),
    ProjectLesson(
        source_project="hermes-agent",
        category="tools",
        lesson="Read-loop prevention stops small models from endlessly reading files",
        what_works="Track consecutive read/search calls. Warn after threshold. Force action-taking.",
        what_fails="Small models get stuck in read-only loops, consuming context without progress.",
        bitter_lesson_alignment=True,
        priority="medium",
        implementation_status="done",
    ),
    ProjectLesson(
        source_project="awesome-hermes-agent (RTK)",
        category="context",
        lesson="Terminal output compression saves 60-90% of bash output tokens",
        what_works="Compress long outputs: keep head + tail, omit middle. Extract error lines from tracebacks.",
        what_fails="Sending full terminal output to small models. Context window fills up in 2-3 bash calls.",
        bitter_lesson_alignment=True,
        priority="medium",
        implementation_status="done",
    ),
    ProjectLesson(
        source_project="hermes-agent",
        category="tools",
        lesson="Dynamic tool schema rebuilding prevents hallucination of unavailable tools",
        what_works="Remove tools from schema when dependencies aren't met. Update descriptions to remove cross-references.",
        what_fails="Showing unavailable tools in schema. Model tries to use them and fails.",
        bitter_lesson_alignment=True,
        priority="medium",
        implementation_status="pending",
    ),
    ProjectLesson(
        source_project="learn-claude-code",
        category="prompt",
        lesson="On-demand skill loading (2-layer) saves 100s of tokens per skill",
        what_works="Layer 1: skill names+descriptions in system prompt. Layer 2: full content loaded on demand via tool call.",
        what_fails="Loading full skill content into system prompt. Wastes context on unused skills.",
        bitter_lesson_alignment=True,
        priority="medium",
        implementation_status="pending",
    ),
    ProjectLesson(
        source_project="hermes-agent-self-evolution",
        category="architecture",
        lesson="Self-evolution via GEPA optimizes prompts/skills based on real outcomes",
        what_works="Evaluate skills on test tasks. Evolve with genetic-pareto optimization. Gate with regression tests.",
        what_fails="Hand-tuning prompts based on intuition. No empirical feedback loop.",
        bitter_lesson_alignment=True,
        priority="low",
        implementation_status="pending",
    ),
    ProjectLesson(
        source_project="kwcode",
        category="small_model",
        lesson="Model capability adaptive strategy: adjust behavior by model size",
        what_works="<10B: force plan mode, max 2 files, search after 1 failure. 10-30B: optional plan, max 4 files. >30B: relaxed.",
        what_fails="Same prompt and strategy for all model sizes. Tiny models overwhelmed, large models underutilized.",
        bitter_lesson_alignment=True,
        priority="high",
        implementation_status="done",
    ),
    ProjectLesson(
        source_project="kaiwu",
        category="architecture",
        lesson="Hardware-aware KV cache selection and context window optimization",
        what_works="Auto-detect hardware, benchmark KV cache options, find largest sustainable context window.",
        what_fails="Manual configuration. OOM errors from context window too large for hardware.",
        bitter_lesson_alignment=True,
        priority="medium",
        implementation_status="pending",
    ),
    ProjectLesson(
        source_project="VibeGPS",
        category="ui",
        lesson="Automatic change tracking generates checkpoint + delta reports between user check-ins",
        what_works="Track what changed after each AI round. Generate HTML/Markdown reports with architecture diagrams.",
        what_fails="User has no idea what the AI actually did. Lost context between sessions.",
        bitter_lesson_alignment=False,
        priority="low",
        implementation_status="pending",
    ),
    ProjectLesson(
        source_project="llm_wiki",
        category="architecture",
        lesson="Knowledge graph with community detection improves retrieval quality",
        what_works="Two-step chain-of-thought ingest. 4-signal relevance model. Louvain community detection.",
        what_fails="Flat document storage. No relationship tracking between concepts.",
        bitter_lesson_alignment=True,
        priority="low",
        implementation_status="pending",
    ),
    ProjectLesson(
        source_project="OpenHarness",
        category="architecture",
        lesson="QueryEngine pattern: clean separation of history, tools, permissions, cost tracking",
        what_works="QueryEngine owns conversation history. Tool registry separate. Permission checker separate. Cost tracker separate.",
        what_fails="Monolithic architecture where everything is coupled. Hard to test, hard to extend.",
        bitter_lesson_alignment=True,
        priority="medium",
        implementation_status="pending",
    ),
    ProjectLesson(
        source_project="Viral_Writer_Skill",
        category="prompt",
        lesson="Structured internal thinking before output dramatically improves quality",
        what_works="Model completes 11 dimensions of analysis internally before producing output. Applied to coding: architecture, edge cases, testing.",
        what_fails="Model jumps straight into coding without planning. Misses edge cases, poor architecture.",
        bitter_lesson_alignment=False,
        priority="low",
        implementation_status="done",
    ),
    ProjectLesson(
        source_project="kwcode",
        category="small_model",
        lesson="Three-stage retry with reflection: normal -> error-first+reflection -> minimal-change",
        what_works="Each retry gets fresh context. Strategy 2: LLM analyzes why it failed. Strategy 3: minimal changes only.",
        what_fails="Retrying with same approach. No root cause analysis. Context pollution from previous attempts.",
        bitter_lesson_alignment=True,
        priority="high",
        implementation_status="pending",
    ),
    ProjectLesson(
        source_project="kwcode",
        category="architecture",
        lesson="Checkpoint system: auto-snapshot before execution, auto-restore on failure",
        what_works="Snapshot files before task. On failure, restore to previous state. Non-blocking, fire-and-forget.",
        what_fails="No rollback capability. Failed tasks leave codebase in broken state.",
        bitter_lesson_alignment=False,
        priority="medium",
        implementation_status="pending",
    ),
    ProjectLesson(
        source_project="hermes-web-ui",
        category="ui",
        lesson="BFF pattern + SSE streaming for real-time response display",
        what_works="Backend-for-Frontend proxies to gateway. SSE for streaming. Multi-session management with grouping.",
        what_fails="Direct API calls from frontend. No streaming. Single session only.",
        bitter_lesson_alignment=True,
        priority="low",
        implementation_status="pending",
    ),
    ProjectLesson(
        source_project="AutoCLI",
        category="tools",
        lesson="Declarative YAML pipelines for web data extraction",
        what_works="fetch -> select -> map -> filter -> sort -> limit. AI-powered adapter generation for any website.",
        what_fails="Hard-coded scrapers for each site. Brittle, unmaintainable.",
        bitter_lesson_alignment=True,
        priority="low",
        implementation_status="pending",
    ),
    ProjectLesson(
        source_project="FreeAskInternet",
        category="tools",
        lesson="Multi-engine search + numbered citation format improves answer quality",
        what_works="SearXNG + DDG parallel search. Content extraction. [citation:x] format in answers.",
        what_fails="Single search engine. No citation tracking. Hallucinated sources.",
        bitter_lesson_alignment=True,
        priority="medium",
        implementation_status="pending",
    ),
]


def get_lessons_by_category(category: str) -> list[ProjectLesson]:
    return [lesson for lesson in CROSS_PROJECT_LESSONS if lesson.category == category]


def get_lessons_by_priority(priority: str) -> list[ProjectLesson]:
    return [lesson for lesson in CROSS_PROJECT_LESSONS if lesson.priority == priority]


def get_bitter_lesson_aligned() -> list[ProjectLesson]:
    return [lesson for lesson in CROSS_PROJECT_LESSONS if lesson.bitter_lesson_alignment]


def get_implementation_status(status: str) -> list[ProjectLesson]:
    return [lesson for lesson in CROSS_PROJECT_LESSONS if lesson.implementation_status == status]


def generate_lessons_report() -> str:
    """Generate a comprehensive lessons learned report."""
    lines = ["=" * 60, "CROSS-PROJECT LESSONS LEARNED REPORT", "=" * 60, ""]
    lines.append(f"Total lessons: {len(CROSS_PROJECT_LESSONS)}")
    lines.append(f"Implemented: {len(get_implementation_status('done'))}")
    lines.append(f"Pending: {len(get_implementation_status('pending'))}")
    lines.append(f"Bitter Lesson aligned: {len(get_bitter_lesson_aligned())}")
    lines.append("")

    categories = ["small_model", "architecture", "context", "tools", "prompt", "ui"]
    for cat in categories:
        cat_lessons = get_lessons_by_category(cat)
        if not cat_lessons:
            continue
        lines.append(f"\n--- {cat.upper()} ---")
        for lesson in cat_lessons:
            status_icon = "✅" if lesson.implementation_status == "done" else "⏳"
            bitter_icon = "🔥" if lesson.bitter_lesson_alignment else "⚠️"
            lines.append(
                f"\n{status_icon} {bitter_icon} [{lesson.priority.upper()}] {lesson.source_project}"
            )
            lines.append(f"   Lesson: {lesson.lesson}")
            lines.append(f"   Works: {lesson.what_works}")
            lines.append(f"   Fails: {lesson.what_fails}")

    lines.append("\n" + "=" * 60)
    lines.append("BITTER LESSON PRINCIPLE")
    lines.append("=" * 60)
    lines.append("")
    lines.append('"The bitter lesson is that methods that leverage computation')
    lines.append("and learning scale better than methods that rely on")
    lines.append('human-engineered knowledge." -- Rich Sutton, 2019')
    lines.append("")
    lines.append("Applied to AI coding assistants:")
    lines.append("1. Let data decide what works, not human assumptions")
    lines.append("2. Computation (search, exploration) > hand-crafted rules")
    lines.append("3. General methods > domain-specific hacks")
    lines.append("4. Learning from experience > human-designed knowledge")
    lines.append("5. Simple + scalable > complex + brittle")

    return "\n".join(lines)
