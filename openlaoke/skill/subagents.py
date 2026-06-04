"""Top-level subagent tool wrappers.

Four dedicated subagent skills — explore, research, review,
security_review — wrap the standard subagent machinery with predefined
prompts and tool allow-lists so the model can dispatch them with one
tool call instead of constructing a custom ``subagent`` invocation.

These are the *affordance > prompt rules* wrappers: naming a tool
``explore`` is more reliable than instructing the model to "use the
subagent tool with type=explore".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SubagentSpec:
    """Configuration for a built-in subagent skill."""

    name: str
    description: str
    system_prompt: str
    allowed_tools: list[str]
    max_steps: int = 20
    run_in_background: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


_EXPLORE_PROMPT = """You are an explore subagent. Your sole job is to investigate
the codebase to answer a single, narrowly-scoped question.

Rules:
- Be quick and shallow. Use the read-only tools (read_file, ls, glob, grep).
- Do not edit any files. If the answer requires a change, return a
  proposal but do not apply it.
- Stop as soon as you have enough information to answer.

Output: a 1-3 paragraph summary, citing the exact file paths and line
numbers you found, followed by a short bullet list of evidence.
"""


_RESEARCH_PROMPT = """You are a research subagent. Your job is to investigate
external knowledge (web pages, documentation, package registries) to
answer a single, narrowly-scoped question.

Rules:
- Prefer fetching official docs or well-known references.
- Cite every claim with the URL you got it from.
- Do not modify any local files.

Output: a concise summary with embedded citations.
"""


_REVIEW_PROMPT = """You are a review subagent. Your job is to read a diff or a
short file and produce a code review.

Rules:
- Read the input carefully. Do not edit files.
- Focus on: correctness, security, performance, readability,
  consistency with the rest of the codebase.
- Cite line numbers for each finding.

Output: a bullet list of findings ordered by severity
(blocker / important / nit). One line per finding.
"""


_SECURITY_REVIEW_PROMPT = """You are a security review subagent. Your job is
to read code and find security vulnerabilities.

Rules:
- Read the input carefully. Do not edit files.
- Look for: injection, path traversal, secret leakage, insecure
  deserialization, unsafe shell invocation, weak cryptography,
  authorization bypasses.
- Cite line numbers for each finding.

Output: a bullet list of findings ordered by severity
(critical / high / medium / low). One line per finding.
"""


SUBAGENT_SKILLS: dict[str, SubagentSpec] = {
    "explore": SubagentSpec(
        name="explore",
        description=(
            "Investigate the codebase to answer a single, narrowly-scoped "
            "question. Read-only; never edits files."
        ),
        system_prompt=_EXPLORE_PROMPT,
        allowed_tools=["read_file", "ls", "glob", "grep"],
        max_steps=15,
    ),
    "research": SubagentSpec(
        name="research",
        description=(
            "Investigate external documentation and references to answer a "
            "single, narrowly-scoped question. Read-only."
        ),
        system_prompt=_RESEARCH_PROMPT,
        allowed_tools=["web_fetch", "web_search", "read_file"],
        max_steps=20,
    ),
    "review": SubagentSpec(
        name="review",
        description=(
            "Read a diff or file and produce a code review. Read-only; never edits files."
        ),
        system_prompt=_REVIEW_PROMPT,
        allowed_tools=["read_file", "ls", "glob", "grep"],
        max_steps=10,
    ),
    "security_review": SubagentSpec(
        name="security_review",
        description=("Read code and find security vulnerabilities. Read-only; never edits files."),
        system_prompt=_SECURITY_REVIEW_PROMPT,
        allowed_tools=["read_file", "ls", "glob", "grep"],
        max_steps=15,
    ),
}


def get_subagent_spec(name: str) -> SubagentSpec | None:
    return SUBAGENT_SKILLS.get(name)
