---
name: source-comparison
description: Compare multiple sources on a topic with consensus and disagreement analysis.
version: 1.0.0
---

# Source Comparison Skill

Produce a comparison matrix across multiple sources on the same topic.

## Workflow

1. Identify key dimensions for comparison
2. Search and gather sources from different types (papers, docs, blogs)
3. Extract claims per dimension per source
4. Build comparison matrix
5. Analyze consensus and disagreements

## Output Structure

```
# Comparison: <topic>

## Comparison Matrix
| Dimension | Source A | Source B | Source C |
|-----------|----------|----------|----------|
| ... | ... | ... | ... |

## Consensus
Points where sources agree.

## Disagreements
Points of conflict with analysis.

## Open Questions
What remains unresolved.

## Sources
Numbered list with URLs.
```
