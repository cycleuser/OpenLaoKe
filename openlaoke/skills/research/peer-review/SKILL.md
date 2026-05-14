---
name: peer-review
description: Simulate peer review with severity-graded feedback and revision plan.
version: 1.0.0
---

# Peer Review Skill

Act as a skeptical but constructive peer reviewer for research artifacts.

## Review Dimensions

- Novelty and contribution
- Clarity and presentation
- Empirical rigor and methodology
- Reproducibility
- Related work positioning
- Claims vs evidence alignment

## Output Format

### Structured Review
- Summary (1-2 paragraphs)
- Strengths [S1, S2, ...]
- Weaknesses [W1 FATAL, W2 MAJOR, W3 MINOR]
- Questions for Authors
- Verdict with confidence score
- Revision Plan

### Inline Annotations
Quote passages and annotate with specific issues.

## Severity Levels

- **FATAL**: Must fix before submission
- **MAJOR**: Should fix, may affect acceptance
- **MINOR**: Polish, nice to fix
