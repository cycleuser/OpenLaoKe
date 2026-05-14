"""Research workflow commands - deepresearch, lit, review, etc.

Inspired by Feynman's research workflows.
Provides slash commands for structured research tasks with provenance tracking.
"""

from __future__ import annotations

import os

from openlaoke.commands.base import CommandContext, CommandResult, SlashCommand
from openlaoke.core.supervisor.provenance import ProvenanceRecord
from openlaoke.core.supervisor.slug_utils import ensure_output_dirs, generate_slug, get_output_paths


class DeepResearchCommand(SlashCommand):
    """Run deep research on a topic with provenance tracking.

    Usage: /deepresearch <topic>
    """

    name = "deepresearch"
    description = "Run thorough, source-heavy investigation on any topic"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip()
        if not args:
            return CommandResult(success=False, message="Usage: /deepresearch <topic>")

        slug = generate_slug(args)
        ensure_output_dirs()
        paths = get_output_paths(slug)

        provenance = ProvenanceRecord(
            topic=args,
            slug=slug,
            plan_path=paths["plan"],
            output_path=paths["output"],
        )

        plan_content = f"""# Research Plan: {args}

## Key Questions
- What are the core concepts and definitions?
- What is the current state of the art?
- What are the open problems and challenges?

## Evidence Needed
- Academic papers and citations
- Technical documentation and benchmarks
- Expert opinions and analyses

## Scale Decision
Direct search for narrow topics, subagents for broad surveys.

## Task Ledger
- [ ] Search academic papers
- [ ] Search web sources
- [ ] Synthesize findings
- [ ] Draft report
- [ ] Add citations
- [ ] Review and verify

## Verification Log
Pending...

## Decision Log
Pending...
"""

        os.makedirs(os.path.dirname(paths["plan"]), exist_ok=True)
        with open(paths["plan"], "w", encoding="utf-8") as f:
            f.write(plan_content)

        provenance.save(os.path.dirname(paths["provenance"]))

        return CommandResult(
            message=f"Deep research plan created for '{args}'\n"
            f"Slug: {slug}\n"
            f"Plan: {paths['plan']}\n"
            f"Output: {paths['output']}\n"
            f"Provenance: {paths['provenance']}\n\n"
            f"Proceed with this deep research plan? Reply 'yes' to continue, or tell me what to change."
        )


class LitReviewCommand(SlashCommand):
    """Run literature review on a topic.

    Usage: /lit <topic>
    """

    name = "lit"
    description = "Literature review with paper search and synthesis"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip()
        if not args:
            return CommandResult(success=False, message="Usage: /lit <topic>")

        slug = generate_slug(args)
        ensure_output_dirs()
        paths = get_output_paths(slug)

        provenance = ProvenanceRecord(
            topic=f"Literature review: {args}",
            slug=slug,
            plan_path=paths["plan"],
            output_path=paths["output"],
        )
        provenance.save(os.path.dirname(paths["provenance"]))

        return CommandResult(
            message=f"Literature review started for '{args}'\n"
            f"Slug: {slug}\n"
            f"Output: {paths['output']}\n"
            f"Provenance: {paths['provenance']}"
        )


class ReviewCommand(SlashCommand):
    """Simulate peer review on an artifact.

    Usage: /review <artifact>
    """

    name = "review"
    description = "Simulated peer review with severity-graded feedback"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip()
        if not args:
            return CommandResult(success=False, message="Usage: /review <artifact>")

        slug = generate_slug(args)
        ensure_output_dirs()
        paths = get_output_paths(slug)

        return CommandResult(
            message=f"Peer review started for '{args}'\n"
            f"Slug: {slug}\n"
            f"Output: {paths['output']}"
        )


class OutputsCommand(SlashCommand):
    """Browse all research artifacts.

    Usage: /outputs
    """

    name = "outputs"
    description = "Browse all research artifacts"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        base_dir = os.getcwd()
        outputs_dir = os.path.join(base_dir, "outputs")
        papers_dir = os.path.join(base_dir, "papers")

        lines = ["## Research Outputs\n"]

        if os.path.exists(outputs_dir):
            for root, dirs, files in os.walk(outputs_dir):
                for f in files:
                    if not f.startswith("."):
                        lines.append(f"- {os.path.join(root, f)}")

        if os.path.exists(papers_dir):
            for f in os.listdir(papers_dir):
                lines.append(f"- {os.path.join(papers_dir, f)}")

        if len(lines) == 1:
            lines.append("No research outputs found.")

        return CommandResult(message="\n".join(lines))
