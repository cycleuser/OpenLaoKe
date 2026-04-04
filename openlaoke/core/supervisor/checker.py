"""Task completion checker - verifies requirements are met."""

from __future__ import annotations

import os
import re
from typing import Any

from openlaoke.core.supervisor.requirements import RequirementCheckResult, TaskRequirements


class TaskCompletionChecker:
    """Checks if task requirements are satisfied.

    Implements various check types:
    - file_exists: Check if output file exists
    - word_count: Check minimum word count
    - structure: Check for required sections
    - contains: Check for required patterns
    - has_numbers: Check for quantitative data
    - files_created: Check for generated files
    - anti_ai_check: Detect AI-typical patterns
    - general: Generic completion check
    """

    AI_PATTERNS = [
        r"^(?:[\d\-\•]\s+[\w\s]+,\s*){3,}$",
        r"^(?:[\d\-\•]\s+[\w\s]+\n){3,}$",
        r"Systems?\s+(?:could|would|should|might)\s+\w+",
        r"Improvements?\s+(?:include|are|would be)",
        r"The\s+main\s+(?:contributions|features|benefits)\s+(?:are|include)",
        r"^(?:In\s+conclusion|To\s+summarize|Overall),",
        r"\b(?:novel|state-of-the-art|cutting-edge|groundbreaking)\b.{0,20}\b(?:approach|method|system|technique)\b",
    ]

    ACADEMIC_QUALITY_MARKERS = [
        r"\[\d+\]",
        r"et\s+al\.",
        r"\d+(?:\.\d+)?%",
        r"Figure\s+\d+",
        r"Table\s+\d+",
        r"Section\s+\d+",
        r":\d+",
    ]

    def __init__(self):
        self._anti_ai_enabled = True

    def enable_anti_ai_check(self, enabled: bool = True) -> None:
        self._anti_ai_enabled = enabled

    async def check_requirement(
        self,
        requirement: TaskRequirements,
        artifacts: dict[str, Any],
    ) -> bool:
        result = await self._check(requirement, artifacts)
        return result.satisfied

    async def _check(
        self,
        requirement: TaskRequirements,
        artifacts: dict[str, Any],
    ) -> RequirementCheckResult:
        check_type = requirement.check_type

        if check_type == "file_exists":
            return self._check_file_exists(requirement, artifacts)
        elif check_type == "word_count":
            return self._check_word_count(requirement, artifacts)
        elif check_type == "structure":
            return self._check_structure(requirement, artifacts)
        elif check_type == "contains":
            return self._check_contains(requirement, artifacts)
        elif check_type == "has_numbers":
            return self._check_has_numbers(requirement, artifacts)
        elif check_type == "files_created":
            return self._check_files_created(requirement, artifacts)
        elif check_type == "anti_ai_check":
            return self._check_anti_ai(requirement, artifacts)
        elif check_type == "references_exist":
            return self._check_references_exist(requirement, artifacts)
        elif check_type == "citations_quality":
            return self._check_citations_quality(requirement, artifacts)
        elif check_type == "general":
            return self._check_general(requirement, artifacts)
        else:
            return RequirementCheckResult(
                requirement=requirement,
                satisfied=False,
                message=f"Unknown check type: {check_type}",
            )

    def _check_file_exists(
        self,
        requirement: TaskRequirements,
        artifacts: dict[str, Any],
    ) -> RequirementCheckResult:
        output_files = artifacts.get("output_files", [])
        content = artifacts.get("content", "")

        if output_files:
            for f in output_files:
                if os.path.exists(f):
                    return RequirementCheckResult(
                        requirement=requirement,
                        satisfied=True,
                        actual_value=f,
                        message=f"File exists: {f}",
                    )

        if content and len(content) > 100:
            return RequirementCheckResult(
                requirement=requirement,
                satisfied=True,
                message="Content generated in memory",
            )

        return RequirementCheckResult(
            requirement=requirement,
            satisfied=False,
            message="No output file found",
        )

    def _check_word_count(
        self,
        requirement: TaskRequirements,
        artifacts: dict[str, Any],
    ) -> RequirementCheckResult:
        content = artifacts.get("content", "")
        threshold = requirement.threshold or 1000

        words = len(content.split())
        satisfied = words >= threshold

        return RequirementCheckResult(
            requirement=requirement,
            satisfied=satisfied,
            actual_value=words,
            message=f"Word count: {words} (required: {threshold})",
        )

    def _check_structure(
        self,
        requirement: TaskRequirements,
        artifacts: dict[str, Any],
    ) -> RequirementCheckResult:
        content = artifacts.get("content", "")
        patterns = requirement.patterns or []

        found = []
        missing = []

        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                found.append(pattern)
            else:
                missing.append(pattern)

        satisfied = len(found) >= len(patterns) * 0.5

        return RequirementCheckResult(
            requirement=requirement,
            satisfied=satisfied,
            actual_value=found,
            message=f"Found sections: {found}, missing: {missing}",
            details={"found": found, "missing": missing},
        )

    def _check_contains(
        self,
        requirement: TaskRequirements,
        artifacts: dict[str, Any],
    ) -> RequirementCheckResult:
        content = artifacts.get("content", "")
        patterns = requirement.patterns or []

        found_count = 0
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                found_count += 1

        satisfied = found_count >= len(patterns) * 0.3

        return RequirementCheckResult(
            requirement=requirement,
            satisfied=satisfied,
            actual_value=found_count,
            message=f"Found {found_count}/{len(patterns)} patterns",
        )

    def _check_has_numbers(
        self,
        requirement: TaskRequirements,
        artifacts: dict[str, Any],
    ) -> RequirementCheckResult:
        content = artifacts.get("content", "")

        numbers = re.findall(r"\d+(?:\.\d+)?(?:%)?", content)
        percentages = re.findall(r"\d+(?:\.\d+)?%", content)
        citations = re.findall(r"\[\d+\]", content)

        has_quantitative = len(numbers) >= 10
        has_percentages = len(percentages) >= 3
        has_citations = len(citations) >= 3

        satisfied = has_quantitative and (has_percentages or has_citations)

        return RequirementCheckResult(
            requirement=requirement,
            satisfied=satisfied,
            actual_value={
                "numbers": len(numbers),
                "percentages": len(percentages),
                "citations": len(citations),
            },
            message=f"Numbers: {len(numbers)}, Percentages: {len(percentages)}, Citations: {len(citations)}",
        )

    def _check_files_created(
        self,
        requirement: TaskRequirements,
        artifacts: dict[str, Any],
    ) -> RequirementCheckResult:
        output_files = artifacts.get("output_files", [])
        patterns = requirement.patterns or ["*.svg", "*.png"]

        found_files = []
        for pattern in patterns:
            if "*" in pattern:
                ext = pattern.replace("*", "")
                for f in output_files:
                    if f.endswith(ext):
                        found_files.append(f)
            else:
                if pattern in output_files:
                    found_files.append(pattern)

        satisfied = len(found_files) > 0

        return RequirementCheckResult(
            requirement=requirement,
            satisfied=satisfied,
            actual_value=found_files,
            message=f"Created files: {found_files}",
        )

    def _check_anti_ai(
        self,
        requirement: TaskRequirements,
        artifacts: dict[str, Any],
    ) -> RequirementCheckResult:
        if not self._anti_ai_enabled:
            return RequirementCheckResult(
                requirement=requirement,
                satisfied=True,
                message="Anti-AI check disabled",
            )

        content = artifacts.get("content", "")

        ai_pattern_count = 0
        for pattern in self.AI_PATTERNS:
            matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
            ai_pattern_count += len(matches)

        quality_marker_count = 0
        for pattern in self.ACADEMIC_QUALITY_MARKERS:
            matches = re.findall(pattern, content)
            quality_marker_count += len(matches)

        lines = content.split("\n")
        bullet_lines = sum(1 for line in lines if re.match(r"^\s*[\d\-\•]", line))
        bullet_ratio = bullet_lines / len(lines) if lines else 0

        score = 0
        issues = []

        if ai_pattern_count > 5:
            issues.append(f"AI-typical phrases: {ai_pattern_count}")
            score -= ai_pattern_count
        else:
            score += 5

        if quality_marker_count > 10:
            score += 10
        elif quality_marker_count > 5:
            score += 5
        else:
            issues.append(f"Few quality markers: {quality_marker_count}")

        if bullet_ratio > 0.3:
            issues.append(f"Too many bullet points: {bullet_ratio:.1%}")
            score -= 5
        else:
            score += 5

        word_count = len(content.split())
        if word_count < 500:
            issues.append(f"Content too short: {word_count} words")
            score -= 10

        paragraphs = [p for p in content.split("\n\n") if len(p.strip()) > 100]
        if len(paragraphs) < 3:
            issues.append(f"Few substantive paragraphs: {len(paragraphs)}")
            score -= 5

        satisfied = score >= 0 and len(issues) <= 2

        return RequirementCheckResult(
            requirement=requirement,
            satisfied=satisfied,
            actual_value={
                "ai_patterns": ai_pattern_count,
                "quality_markers": quality_marker_count,
                "bullet_ratio": bullet_ratio,
                "score": score,
            },
            message=f"Anti-AI score: {score}. Issues: {issues}",
            details={"issues": issues},
        )

    def _check_general(
        self,
        requirement: TaskRequirements,
        artifacts: dict[str, Any],
    ) -> RequirementCheckResult:
        content = artifacts.get("content", "")
        output_files = artifacts.get("output_files", [])

        has_content = len(content) > 100
        has_files = len(output_files) > 0

        satisfied = has_content or has_files

        return RequirementCheckResult(
            requirement=requirement,
            satisfied=satisfied,
            message=f"Has content: {has_content}, Has files: {has_files}",
        )

    def _check_references_exist(
        self,
        requirement: TaskRequirements,
        artifacts: dict[str, Any],
    ) -> RequirementCheckResult:
        content = artifacts.get("content", "")
        working_dir = artifacts.get("working_dir", os.getcwd())

        pdf_dir = os.path.join(working_dir, "pdf")

        citations = re.findall(r"\[(\d+)\]", content)
        unique_citations = set(citations)

        pdf_files = []
        if os.path.exists(pdf_dir):
            pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith(".pdf")]

        satisfied = len(pdf_files) >= len(unique_citations) or len(pdf_files) >= 3

        return RequirementCheckResult(
            requirement=requirement,
            satisfied=satisfied,
            actual_value={
                "citations_count": len(unique_citations),
                "pdfs_downloaded": len(pdf_files),
                "pdf_dir": pdf_dir,
            },
            message=f"Citations: {len(unique_citations)}, PDFs downloaded: {len(pdf_files)} in {pdf_dir}",
            details={"pdf_files": pdf_files},
        )

    def _check_citations_quality(
        self,
        requirement: TaskRequirements,
        artifacts: dict[str, Any],
    ) -> RequirementCheckResult:
        content = artifacts.get("content", "")

        citations = re.findall(r"\[(\d+)\]", content)
        unique_citations = set(citations) if citations else set()

        has_arxiv_refs = bool(re.search(r"arXiv:\d{4}\.\d{4,5}", content))
        has_doi_refs = bool(re.search(r"10\.\d{4,}/[^\s\]]+", content))
        has_author_year = bool(re.search(r"[A-Z][a-z]+\s+et\s+al\.\s*\[\d+\]", content))
        has_proper_citation_format = len(unique_citations) >= 3

        quality_score = sum(
            [
                has_proper_citation_format * 2,
                has_arxiv_refs,
                has_doi_refs,
                has_author_year,
            ]
        )

        satisfied = quality_score >= 2

        return RequirementCheckResult(
            requirement=requirement,
            satisfied=satisfied,
            actual_value={
                "unique_citations": len(unique_citations),
                "has_arxiv": has_arxiv_refs,
                "has_doi": has_doi_refs,
                "has_author_year": has_author_year,
                "quality_score": quality_score,
            },
            message=f"Citation quality score: {quality_score}/5. "
            f"Unique citations: {len(unique_citations)}, "
            f"arXiv: {has_arxiv_refs}, DOI: {has_doi_refs}",
        )
