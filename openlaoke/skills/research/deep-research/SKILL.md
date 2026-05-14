---
name: deep-research
description: Run a thorough, source-heavy investigation on any topic. Produces a cited research brief with provenance tracking.
version: 1.0.0
---

# Deep Research Skill

Run a comprehensive research investigation with evidence gathering, drafting, citation, and review.

## Workflow

1. **Plan** - Derive a slug from topic, create plan artifact
2. **Gather Evidence** - Search papers, web, repos using researcher agents
3. **Draft** - Write report from research notes
4. **Cite** - Add inline citations, verify URLs
5. **Review** - Simulated peer review with severity grading
6. **Deliver** - Final output with provenance sidecar

## Output Convention

All files use the slug prefix:
- Plan: `outputs/.plans/<slug>.md`
- Draft: `outputs/.drafts/<slug>-draft.md`
- Cited: `outputs/.drafts/<slug>-cited.md`
- Output: `outputs/<slug>.md`
- Provenance: `outputs/<slug>.provenance.md`

## Provenance Requirements

Every deep research output must include a `.provenance.md` sidecar with:
- Evidence table with numbered sources
- Verification status (PASS / PASS_WITH_NOTES / BLOCKED)
- Sources consulted, accepted, rejected
- Open questions and blocked checks

## Scale Decision

- **Direct search**: narrow "what is X" questions, 3-10 tool calls
- **Subagents**: broad surveys, multi-faceted topics, 3-6 researcher agents

## Integrity Rules

1. Never fabricate a source
2. URL or it didn't happen
3. Mark verification status honestly
4. Remove unsupported claims, don't smooth over gaps
