"""Slug generation and output path utilities.

Inspired by Feynman's file naming conventions.
Provides deterministic slug generation from topics and standardized output paths.
"""

from __future__ import annotations

import os
import re
import time


def generate_slug(topic: str, max_words: int = 5) -> str:
    """Generate a short slug from a topic.

    Rules:
    - lowercase
    - hyphens as separators
    - no filler words
    - max_words words (default 5)
    - ASCII only (CJK converted to pinyin-like representation)

    Examples:
        "What do we know about scaling laws?" -> "scaling-laws"
        "mechanistic interpretability survey" -> "mechanistic-interpretability-survey"
        "RLHF alternatives comparison" -> "rlhf-alternatives-comparison"
    """
    filler_words = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "like", "through", "after", "over", "between", "out",
        "against", "during", "without", "before", "under", "around", "among",
        "what", "how", "why", "when", "where", "who", "which", "that",
        "we", "our", "us", "i", "me", "my", "you", "your", "he", "him",
        "his", "she", "her", "it", "its", "they", "them", "their",
        "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
        "neither", "each", "every", "all", "any", "few", "more", "most",
        "other", "some", "such", "no", "only", "own", "same", "than",
        "too", "very", "just", "about", "up", "if", "then", "know", "see", "look", "get", "go", "make", "take", "come", "give",
    }

    has_cjk = any('\u4e00' <= c <= '\u9fff' for c in topic)

    topic = topic.lower()
    topic = re.sub(r"[^\w\s-]", " ", topic)

    words = topic.split()
    meaningful_words = [w for w in words if w not in filler_words and len(w) > 1]

    if not meaningful_words and has_cjk:
        meaningful_words = [w for w in words if len(w) > 0]

    slug_words = meaningful_words[:max_words]
    slug = "-".join(slug_words)

    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    slug = re.sub(r"[^\w\u4e00-\u9fff-]", "", slug)

    if not slug:
        slug = f"topic-{int(time.time() * 1000) % 100000}"

    return slug


def get_output_paths(
    slug: str,
    base_dir: str | None = None,
    output_type: str = "research",
) -> dict[str, str]:
    """Get standardized output paths for a research workflow.

    Returns dict with keys:
    - plan: outputs/.plans/<slug>.md
    - draft: outputs/.drafts/<slug>-draft.md
    - cited: outputs/.drafts/<slug>-cited.md
    - output: outputs/<slug>.md (or papers/<slug>.md for paper-style)
    - provenance: outputs/<slug>.provenance.md
    - verification: outputs/.drafts/<slug>-verification.md
    - research_web: outputs/.drafts/<slug>-research-web.md
    - research_papers: outputs/.drafts/<slug>-research-papers.md
    """
    if base_dir is None:
        base_dir = os.getcwd()

    if output_type == "paper":
        output_path = os.path.join(base_dir, "papers", f"{slug}.md")
        provenance_path = os.path.join(base_dir, "papers", f"{slug}.provenance.md")
    else:
        output_path = os.path.join(base_dir, "outputs", f"{slug}.md")
        provenance_path = os.path.join(base_dir, "outputs", f"{slug}.provenance.md")

    return {
        "plan": os.path.join(base_dir, "outputs", ".plans", f"{slug}.md"),
        "draft": os.path.join(base_dir, "outputs", ".drafts", f"{slug}-draft.md"),
        "cited": os.path.join(base_dir, "outputs", ".drafts", f"{slug}-cited.md"),
        "output": output_path,
        "provenance": provenance_path,
        "verification": os.path.join(base_dir, "outputs", ".drafts", f"{slug}-verification.md"),
        "research_web": os.path.join(base_dir, "outputs", ".drafts", f"{slug}-research-web.md"),
        "research_papers": os.path.join(base_dir, "outputs", ".drafts", f"{slug}-research-papers.md"),
    }


def ensure_output_dirs(base_dir: str | None = None) -> None:
    """Create all required output directories."""
    if base_dir is None:
        base_dir = os.getcwd()

    dirs = [
        os.path.join(base_dir, "outputs"),
        os.path.join(base_dir, "outputs", ".plans"),
        os.path.join(base_dir, "outputs", ".drafts"),
        os.path.join(base_dir, "papers"),
    ]

    for d in dirs:
        os.makedirs(d, exist_ok=True)


def validate_slug(slug: str) -> bool:
    """Validate slug format."""
    if not slug:
        return False
    if len(slug) > 100:
        return False
    return bool(re.match(r"^[a-z0-9\u4e00-\u9fff]+(-[a-z0-9\u4e00-\u9fff]+)*$", slug))
