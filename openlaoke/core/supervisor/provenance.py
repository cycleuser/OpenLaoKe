"""Provenance tracking system for research outputs.

Inspired by Feynman's provenance sidecar pattern.
Tracks source accounting, verification status, and artifact lineage.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class VerificationStatus(StrEnum):
    PASS = "PASS"
    PASS_WITH_NOTES = "PASS_WITH_NOTES"
    BLOCKED = "BLOCKED"
    UNVERIFIED = "UNVERIFIED"
    INFERRED = "INFERRED"


class SourceType(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    SELF_REPORTED = "self_reported"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class SourceEntry:
    """A single source in the evidence table."""

    source_id: int
    title: str
    url: str
    key_claim: str
    source_type: SourceType = SourceType.SECONDARY
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    accessed_at: str = ""

    def __post_init__(self) -> None:
        if not self.accessed_at:
            self.accessed_at = time.strftime("%Y-%m-%d %H:%M:%S")

    def to_markdown_row(self) -> str:
        return (
            f"| {self.source_id} | {self.title} | {self.url} | "
            f"{self.key_claim} | {self.source_type.value} | {self.confidence.value} |"
        )


@dataclass
class VerificationCheck:
    """Record of a specific verification check."""

    check_type: str
    claim: str
    status: VerificationStatus
    evidence: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_markdown(self) -> str:
        status_icon = {
            VerificationStatus.PASS: "[PASS]",
            VerificationStatus.PASS_WITH_NOTES: "[PASS*]",
            VerificationStatus.BLOCKED: "[BLOCKED]",
            VerificationStatus.UNVERIFIED: "[UNVERIFIED]",
            VerificationStatus.INFERRED: "[INFERRED]",
        }.get(self.status, "[?]")
        return f"- {status_icon} {self.check_type}: {self.claim}"


@dataclass
class ProvenanceRecord:
    """Complete provenance sidecar for a research output."""

    topic: str
    slug: str
    date: str = ""
    output_path: str = ""
    plan_path: str = ""
    verification: VerificationStatus = VerificationStatus.UNVERIFIED

    sources_consulted: list[SourceEntry] = field(default_factory=list)
    sources_accepted: list[int] = field(default_factory=list)
    sources_rejected: list[str] = field(default_factory=list)

    research_rounds: int = 0
    verification_checks: list[VerificationCheck] = field(default_factory=list)

    blocked_checks: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.date:
            self.date = time.strftime("%Y-%m-%d")

    def add_source(
        self,
        source_id: int,
        title: str,
        url: str,
        key_claim: str,
        source_type: SourceType = SourceType.SECONDARY,
        confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
    ) -> None:
        self.sources_consulted.append(
            SourceEntry(
                source_id=source_id,
                title=title,
                url=url,
                key_claim=key_claim,
                source_type=source_type,
                confidence=confidence,
            )
        )

    def accept_source(self, source_id: int) -> None:
        if source_id not in self.sources_accepted:
            self.sources_accepted.append(source_id)

    def reject_source(self, reason: str) -> None:
        self.sources_rejected.append(reason)

    def add_verification_check(
        self,
        check_type: str,
        claim: str,
        status: VerificationStatus,
        evidence: str = "",
    ) -> None:
        self.verification_checks.append(
            VerificationCheck(
                check_type=check_type,
                claim=claim,
                status=status,
                evidence=evidence,
            )
        )
        if status == VerificationStatus.BLOCKED:
            self.blocked_checks.append(f"{check_type}: {claim}")

    def compute_verification_status(self) -> VerificationStatus:
        if not self.verification_checks:
            return VerificationStatus.UNVERIFIED

        has_blocked = any(c.status == VerificationStatus.BLOCKED for c in self.verification_checks)
        has_unverified = any(
            c.status in (VerificationStatus.UNVERIFIED, VerificationStatus.INFERRED)
            for c in self.verification_checks
        )

        if has_blocked:
            self.verification = VerificationStatus.BLOCKED
        elif has_unverified:
            self.verification = VerificationStatus.PASS_WITH_NOTES
        else:
            self.verification = VerificationStatus.PASS

        return self.verification

    def to_markdown(self) -> str:
        lines = [
            f"# Provenance: {self.topic}",
            "",
            f"- **Date:** {self.date}",
            f"- **Slug:** {self.slug}",
            f"- **Rounds:** {self.research_rounds}",
            f"- **Sources consulted:** {len(self.sources_consulted)}",
            f"- **Sources accepted:** {len(self.sources_accepted)}",
            f"- **Sources rejected:** {len(self.sources_rejected)}",
            f"- **Verification:** {self.verification.value}",
        ]

        if self.plan_path:
            lines.append(f"- **Plan:** {self.plan_path}")
        if self.output_path:
            lines.append(f"- **Output:** {self.output_path}")

        lines.append("")
        lines.append("## Evidence Table")
        lines.append("")
        lines.append("| # | Source | URL | Key claim | Type | Confidence |")
        lines.append("|---|--------|-----|-----------|------|------------|")

        for source in self.sources_consulted:
            lines.append(source.to_markdown_row())

        if self.verification_checks:
            lines.append("")
            lines.append("## Verification Log")
            lines.append("")
            for check in self.verification_checks:
                lines.append(check.to_markdown())

        if self.blocked_checks:
            lines.append("")
            lines.append("## Blocked Checks")
            lines.append("")
            for blocked in self.blocked_checks:
                lines.append(f"- {blocked}")

        if self.open_questions:
            lines.append("")
            lines.append("## Open Questions")
            lines.append("")
            for q in self.open_questions:
                lines.append(f"- {q}")

        if self.sources_rejected:
            lines.append("")
            lines.append("## Rejected Sources")
            lines.append("")
            for reason in self.sources_rejected:
                lines.append(f"- {reason}")

        if self.metadata:
            lines.append("")
            lines.append("## Metadata")
            lines.append("")
            for key, value in self.metadata.items():
                lines.append(f"- **{key}:** {value}")

        lines.append("")
        return "\n".join(lines)

    def save(self, output_dir: str | None = None) -> str:
        if output_dir is None:
            output_dir = os.path.join(os.path.expanduser("~/.openlaoke"), "outputs")
        os.makedirs(output_dir, exist_ok=True)

        file_path = os.path.join(output_dir, f"{self.slug}.provenance.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.to_markdown())

        self.metadata["provenance_file"] = file_path
        return file_path

    @classmethod
    def load(cls, file_path: str) -> ProvenanceRecord:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        record = cls(topic="Unknown", slug="unknown")

        in_evidence_table = False

        for line in content.split("\n"):
            if line.startswith("# Provenance:"):
                record.topic = line.replace("# Provenance:", "").strip()
            elif line.startswith("- **Date:**"):
                record.date = line.split("**Date:**")[1].strip()
            elif line.startswith("- **Slug:**"):
                record.slug = line.split("**Slug:**")[1].strip()
            elif line.startswith("- **Rounds:**"):
                record.research_rounds = int(line.split("**Rounds:**")[1].strip())
            elif line.startswith("- **Verification:**"):
                status = line.split("**Verification:**")[1].strip()
                try:
                    record.verification = VerificationStatus(status)
                except ValueError:
                    record.verification = VerificationStatus.UNVERIFIED
            elif line.startswith("## Evidence Table"):
                in_evidence_table = True
            elif line.startswith("## "):
                in_evidence_table = False
            elif in_evidence_table and line.startswith("|") and not line.startswith("| #"):
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 6:
                    try:
                        source_id = int(parts[0])
                        record.sources_consulted.append(
                            SourceEntry(
                                source_id=source_id,
                                title=parts[1],
                                url=parts[2],
                                key_claim=parts[3],
                                source_type=SourceType(parts[4])
                                if parts[4] in SourceType._value2member_map_
                                else SourceType.SECONDARY,
                                confidence=ConfidenceLevel(parts[5])
                                if parts[5] in ConfidenceLevel._value2member_map_
                                else ConfidenceLevel.MEDIUM,
                            )
                        )
                    except (ValueError, IndexError):
                        pass

        return record
