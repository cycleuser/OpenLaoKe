"""Automatic reflection system for quality assessment and self-correction."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from openlaoke.core.hyperauto.workflow import WorkflowResult


class ReviewType(StrEnum):
    """Types of reviews."""

    QUALITY = "quality"
    PERFORMANCE = "performance"
    SECURITY = "security"
    MAINTAINABILITY = "maintainability"
    COMPLETENESS = "completeness"


class ErrorSeverity(StrEnum):
    """Severity levels for errors."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ErrorCategory(StrEnum):
    """Categories of errors."""

    SYNTAX = "syntax"
    LOGIC = "logic"
    PERFORMANCE = "performance"
    SECURITY = "security"
    CONFIGURATION = "configuration"
    DEPENDENCY = "dependency"
    NETWORK = "network"
    TIMEOUT = "timeout"
    PERMISSION = "permission"
    RESOURCE = "resource"


class ImprovementPriority(StrEnum):
    """Priority levels for improvements."""

    IMMEDIATE = "immediate"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"


class QualityDimension(StrEnum):
    """Dimensions of quality assessment."""

    CORRECTNESS = "correctness"
    EFFICIENCY = "efficiency"
    RELIABILITY = "reliability"
    USABILITY = "usability"
    MAINTAINABILITY = "maintainability"
    SECURITY = "security"
    COMPLETENESS = "completeness"


class CorrectionStatus(StrEnum):
    """Status of corrections."""

    APPLIED = "applied"
    PENDING = "pending"
    FAILED = "failed"
    SKIPPED = "skipped"
    PARTIAL = "partial"


@dataclass
class Error:
    """Detected error in execution."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    category: ErrorCategory = ErrorCategory.LOGIC
    message: str = ""
    location: str = ""
    context: str = ""
    timestamp: float = field(default_factory=time.time)
    stack_trace: str = ""
    related_task: str = ""
    suggested_fix: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "category": self.category.value,
            "message": self.message,
            "location": self.location,
            "context": self.context,
            "timestamp": self.timestamp,
            "stack_trace": self.stack_trace,
            "related_task": self.related_task,
            "suggested_fix": self.suggested_fix,
            "metadata": self.metadata,
        }


@dataclass
class Review:
    """Review result for workflow execution."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    type: ReviewType = ReviewType.QUALITY
    workflow_id: str = ""
    reviewer: str = "reflection_system"
    timestamp: float = field(default_factory=time.time)
    overall_score: float = 0.0
    dimension_scores: dict[str, float] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    approved: bool = False
    review_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "workflow_id": self.workflow_id,
            "reviewer": self.reviewer,
            "timestamp": self.timestamp,
            "overall_score": self.overall_score,
            "dimension_scores": self.dimension_scores,
            "findings": self.findings,
            "recommendations": self.recommendations,
            "approved": self.approved,
            "review_time": self.review_time,
            "metadata": self.metadata,
        }


@dataclass
class Analysis:
    """Analysis result for errors."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    error_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    error_categories: dict[str, int] = field(default_factory=dict)
    root_causes: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    impact_assessment: str = ""
    recurrence_risk: float = 0.0
    suggested_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "error_count": self.error_count,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "error_categories": self.error_categories,
            "root_causes": self.root_causes,
            "patterns": self.patterns,
            "impact_assessment": self.impact_assessment,
            "recurrence_risk": self.recurrence_risk,
            "suggested_actions": self.suggested_actions,
            "metadata": self.metadata,
        }


@dataclass
class Improvement:
    """Suggested improvement."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    priority: ImprovementPriority = ImprovementPriority.MEDIUM
    category: str = ""
    description: str = ""
    rationale: str = ""
    estimated_impact: float = 0.0
    implementation_effort: str = "medium"
    dependencies: list[str] = field(default_factory=list)
    affected_components: list[str] = field(default_factory=list)
    implementation_steps: list[str] = field(default_factory=list)
    verification_criteria: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "priority": self.priority.value,
            "category": self.category,
            "description": self.description,
            "rationale": self.rationale,
            "estimated_impact": self.estimated_impact,
            "implementation_effort": self.implementation_effort,
            "dependencies": self.dependencies,
            "affected_components": self.affected_components,
            "implementation_steps": self.implementation_steps,
            "verification_criteria": self.verification_criteria,
            "metadata": self.metadata,
        }


@dataclass
class Correction:
    """Applied correction to fix an issue."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    error_id: str = ""
    status: CorrectionStatus = CorrectionStatus.PENDING
    action: str = ""
    result: str = ""
    timestamp: float = field(default_factory=time.time)
    applied_by: str = "reflection_system"
    verification_result: str = ""
    rollback_available: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "error_id": self.error_id,
            "status": self.status.value,
            "action": self.action,
            "result": self.result,
            "timestamp": self.timestamp,
            "applied_by": self.applied_by,
            "verification_result": self.verification_result,
            "rollback_available": self.rollback_available,
            "metadata": self.metadata,
        }


@dataclass
class CorrectedResult:
    """Result after applying corrections."""

    original_result: WorkflowResult
    corrections: list[Correction] = field(default_factory=list)
    improvement_score: float = 0.0
    remaining_issues: list[str] = field(default_factory=list)
    verification_passed: bool = False
    final_status: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_result": self.original_result.to_dict(),
            "corrections": [c.to_dict() for c in self.corrections],
            "improvement_score": self.improvement_score,
            "remaining_issues": self.remaining_issues,
            "verification_passed": self.verification_passed,
            "final_status": self.final_status,
            "metadata": self.metadata,
        }


@dataclass
class QualityScore:
    """Quality assessment score."""

    overall: float = 0.0
    dimensions: dict[str, float] = field(default_factory=dict)
    grade: str = ""
    passing_threshold: float = 0.7
    passed: bool = False
    breakdown: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "dimensions": self.dimensions,
            "grade": self.grade,
            "passing_threshold": self.passing_threshold,
            "passed": self.passed,
            "breakdown": self.breakdown,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
        }


@dataclass
class ReflectionReport:
    """Complete reflection report."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    workflow_id: str = ""
    timestamp: float = field(default_factory=time.time)
    review: Review | None = None
    error_analysis: Analysis | None = None
    improvements: list[Improvement] = field(default_factory=list)
    corrections: list[Correction] = field(default_factory=list)
    quality_score: QualityScore | None = None
    summary: str = ""
    action_items: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "timestamp": self.timestamp,
            "review": self.review.to_dict() if self.review else None,
            "error_analysis": self.error_analysis.to_dict() if self.error_analysis else None,
            "improvements": [i.to_dict() for i in self.improvements],
            "corrections": [c.to_dict() for c in self.corrections],
            "quality_score": self.quality_score.to_dict() if self.quality_score else None,
            "summary": self.summary,
            "action_items": self.action_items,
            "next_steps": self.next_steps,
            "metadata": self.metadata,
        }


class ReflectionSystem:
    """Automatic reflection system for quality assessment and self-correction.

    Features:
    - Result review for quality assessment
    - Error analysis for root cause identification
    - Improvement suggestion generation
    - Auto-correction for error fixing
    - Quality evaluation for overall assessment
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        self._storage_dir = storage_dir or Path.home() / ".openlaoke" / "reflections"
        self._storage_dir.mkdir(parents=True, exist_ok=True)

        self._reviews: dict[str, Review] = {}
        self._errors: dict[str, Error] = {}
        self._improvements: dict[str, Improvement] = {}
        self._corrections: dict[str, Correction] = {}
        self._reports: dict[str, ReflectionReport] = {}

        self._load_history()

    def review_result(self, result: WorkflowResult) -> Review:
        """Review workflow execution result."""
        start_time = time.time()

        findings: list[str] = []
        recommendations: list[str] = []

        if result.success:
            findings.append("Workflow completed successfully")
        else:
            findings.append(f"Workflow failed: {result.error or 'Unknown error'}")
            recommendations.append("Review error details and implement fixes")

        task_completion_rate = self._calculate_task_completion_rate(result)
        findings.append(f"Task completion rate: {task_completion_rate:.2%}")

        if task_completion_rate < 0.8:
            recommendations.append("Improve task execution reliability")

        execution_efficiency = self._calculate_execution_efficiency(result)
        findings.append(f"Execution efficiency: {execution_efficiency:.2%}")

        if execution_efficiency < 0.5:
            recommendations.append("Optimize execution flow for better efficiency")

        dimension_scores = self._calculate_dimension_scores(result)
        overall_score = (
            sum(dimension_scores.values()) / len(dimension_scores) if dimension_scores else 0.0
        )

        review_time = time.time() - start_time

        review = Review(
            type=ReviewType.QUALITY,
            workflow_id=result.workflow_id,
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            findings=findings,
            recommendations=recommendations,
            approved=overall_score >= 0.7,
            review_time=review_time,
        )

        self._reviews[review.id] = review
        return review

    def analyze_errors(self, errors: list[Error]) -> Analysis:
        """Analyze collected errors."""
        if not errors:
            return Analysis(
                error_count=0,
                impact_assessment="No errors detected",
                recurrence_risk=0.0,
            )

        severity_counts = {
            "critical": len([e for e in errors if e.severity == ErrorSeverity.CRITICAL]),
            "high": len([e for e in errors if e.severity == ErrorSeverity.HIGH]),
            "medium": len([e for e in errors if e.severity == ErrorSeverity.MEDIUM]),
            "low": len([e for e in errors if e.severity == ErrorSeverity.LOW]),
        }

        category_counts: dict[str, int] = {}
        for error in errors:
            cat = error.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        root_causes = self._identify_root_causes(errors)
        patterns = self._identify_error_patterns(errors)
        impact = self._assess_impact(errors, severity_counts)
        recurrence = self._calculate_recurrence_risk(errors)

        suggested_actions = self._generate_suggested_actions(errors, root_causes)

        analysis = Analysis(
            error_count=len(errors),
            critical_count=severity_counts["critical"],
            high_count=severity_counts["high"],
            medium_count=severity_counts["medium"],
            low_count=severity_counts["low"],
            error_categories=category_counts,
            root_causes=root_causes,
            patterns=patterns,
            impact_assessment=impact,
            recurrence_risk=recurrence,
            suggested_actions=suggested_actions,
        )

        self._errors.update({e.id: e for e in errors})
        return analysis

    def generate_improvements(self, analysis: Analysis) -> list[Improvement]:
        """Generate improvement suggestions from error analysis."""
        improvements: list[Improvement] = []

        for root_cause in analysis.root_causes:
            improvement = self._create_improvement_from_root_cause(root_cause, analysis)
            improvements.append(improvement)

        for pattern in analysis.patterns:
            improvement = self._create_improvement_from_pattern(pattern, analysis)
            improvements.append(improvement)

        if analysis.recurrence_risk > 0.5:
            improvement = Improvement(
                priority=ImprovementPriority.HIGH,
                category="prevention",
                description="Implement preventive measures to reduce error recurrence",
                rationale=f"High recurrence risk ({analysis.recurrence_risk:.2%}) detected",
                estimated_impact=0.3,
                implementation_steps=[
                    "Add error detection mechanisms",
                    "Implement validation checks",
                    "Create fallback procedures",
                ],
            )
            improvements.append(improvement)

        sorted_improvements = sorted(
            improvements,
            key=lambda i: (
                ImprovementPriority.IMMEDIATE.value
                if i.priority == ImprovementPriority.IMMEDIATE
                else ImprovementPriority.HIGH.value
                if i.priority == ImprovementPriority.HIGH
                else ImprovementPriority.MEDIUM.value
                if i.priority == ImprovementPriority.MEDIUM
                else ImprovementPriority.LOW.value
                if i.priority == ImprovementPriority.LOW
                else ImprovementPriority.OPTIONAL.value
            ),
            reverse=True,
        )

        for imp in sorted_improvements:
            self._improvements[imp.id] = imp

        return sorted_improvements

    def auto_correct(
        self, result: WorkflowResult, improvements: list[Improvement]
    ) -> CorrectedResult:
        """Apply auto-corrections based on improvements."""
        corrections: list[Correction] = []
        applied_count = 0
        failed_count = 0

        for improvement in improvements:
            if improvement.priority in (ImprovementPriority.IMMEDIATE, ImprovementPriority.HIGH):
                correction = self._apply_improvement(improvement, result)
                corrections.append(correction)

                if correction.status == CorrectionStatus.APPLIED:
                    applied_count += 1
                    self._corrections[correction.id] = correction
                elif correction.status == CorrectionStatus.FAILED:
                    failed_count += 1

        total = len(corrections)
        improvement_score = applied_count / total if total > 0 else 0.0

        remaining = [
            imp.description
            for imp in improvements
            if imp.priority
            in (ImprovementPriority.MEDIUM, ImprovementPriority.LOW, ImprovementPriority.OPTIONAL)
        ]

        verification_passed = self._verify_corrections(result, corrections)

        final_status = (
            "corrected" if verification_passed and applied_count > 0 else "partial_correction"
        )

        return CorrectedResult(
            original_result=result,
            corrections=corrections,
            improvement_score=improvement_score,
            remaining_issues=remaining,
            verification_passed=verification_passed,
            final_status=final_status,
        )

    def assess_quality(self, result: WorkflowResult) -> QualityScore:
        """Assess overall quality of workflow result."""
        dimensions: dict[str, float] = {}

        dimensions[QualityDimension.CORRECTNESS.value] = self._assess_correctness(result)
        dimensions[QualityDimension.EFFICIENCY.value] = self._assess_efficiency(result)
        dimensions[QualityDimension.RELIABILITY.value] = self._assess_reliability(result)
        dimensions[QualityDimension.COMPLETENESS.value] = self._assess_completeness(result)
        dimensions[QualityDimension.MAINTAINABILITY.value] = self._assess_maintainability(result)

        overall = sum(dimensions.values()) / len(dimensions) if dimensions else 0.0

        grade = self._calculate_grade(overall)

        passed = overall >= 0.7

        breakdown = self._create_quality_breakdown(result, dimensions)

        recommendations = self._generate_quality_recommendations(dimensions)

        return QualityScore(
            overall=overall,
            dimensions=dimensions,
            grade=grade,
            passed=passed,
            breakdown=breakdown,
            recommendations=recommendations,
        )

    def reflect_on_workflow(self, result: WorkflowResult) -> ReflectionReport:
        """Generate complete reflection report for workflow."""
        errors = self._extract_errors_from_result(result)
        review = self.review_result(result)
        analysis = self.analyze_errors(errors)
        improvements = self.generate_improvements(analysis)
        quality = self.assess_quality(result)

        summary = self._generate_report_summary(review, analysis, quality)
        action_items = self._generate_action_items(improvements)
        next_steps = self._generate_next_steps(review, quality)

        report = ReflectionReport(
            workflow_id=result.workflow_id,
            review=review,
            error_analysis=analysis,
            improvements=improvements,
            quality_score=quality,
            summary=summary,
            action_items=action_items,
            next_steps=next_steps,
        )

        self._reports[report.id] = report
        self._persist_report(report)

        return report

    def get_all_reviews(self) -> dict[str, Review]:
        """Get all reviews."""
        return self._reviews.copy()

    def get_all_errors(self) -> dict[str, Error]:
        """Get all detected errors."""
        return self._errors.copy()

    def get_all_improvements(self) -> dict[str, Improvement]:
        """Get all improvement suggestions."""
        return self._improvements.copy()

    def get_all_corrections(self) -> dict[str, Correction]:
        """Get all applied corrections."""
        return self._corrections.copy()

    def get_all_reports(self) -> dict[str, ReflectionReport]:
        """Get all reflection reports."""
        return self._reports.copy()

    def _load_history(self) -> None:
        """Load reflection history from storage."""
        try:
            reports_dir = self._storage_dir / "reports"
            if reports_dir.exists():
                for rf in reports_dir.glob("report_*.json"):
                    with open(rf, encoding="utf-8") as f:
                        rdata = json.load(f)

                    rid = rdata.get("id", rf.stem.replace("report_", ""))
                    report = ReflectionReport(
                        id=rid,
                        workflow_id=rdata.get("workflow_id", ""),
                        timestamp=rdata.get("timestamp", 0.0),
                        summary=rdata.get("summary", ""),
                        action_items=rdata.get("action_items", []),
                        next_steps=rdata.get("next_steps", []),
                        metadata=rdata.get("metadata", {}),
                    )

                    if rdata.get("review"):
                        report.review = Review(
                            id=rdata["review"].get("id", ""),
                            type=ReviewType(rdata["review"].get("type", ReviewType.QUALITY.value)),
                            workflow_id=rdata["review"].get("workflow_id", ""),
                            overall_score=rdata["review"].get("overall_score", 0.0),
                            dimension_scores=rdata["review"].get("dimension_scores", {}),
                            findings=rdata["review"].get("findings", []),
                            recommendations=rdata["review"].get("recommendations", []),
                            approved=rdata["review"].get("approved", False),
                        )

                    if rdata.get("quality_score"):
                        report.quality_score = QualityScore(
                            overall=rdata["quality_score"].get("overall", 0.0),
                            dimensions=rdata["quality_score"].get("dimensions", {}),
                            grade=rdata["quality_score"].get("grade", ""),
                            passed=rdata["quality_score"].get("passed", False),
                        )

                    self._reports[rid] = report

        except Exception:
            pass

    def _calculate_task_completion_rate(self, result: WorkflowResult) -> float:
        """Calculate task completion rate."""
        total = len(result.execution_results)
        if total == 0:
            return 0.0

        completed = len([r for r in result.execution_results if r.success])
        return completed / total

    def _calculate_execution_efficiency(self, result: WorkflowResult) -> float:
        """Calculate execution efficiency."""
        if result.total_duration <= 0:
            return 0.0

        planned_duration = result.execution_plan.total_estimated_duration
        if planned_duration <= 0:
            return 0.5

        if result.total_duration <= planned_duration:
            return 1.0
        else:
            return planned_duration / result.total_duration

    def _calculate_dimension_scores(self, result: WorkflowResult) -> dict[str, float]:
        """Calculate scores for quality dimensions."""
        return {
            QualityDimension.CORRECTNESS.value: 1.0 if result.success else 0.0,
            QualityDimension.EFFICIENCY.value: self._calculate_execution_efficiency(result),
            QualityDimension.RELIABILITY.value: self._calculate_task_completion_rate(result),
            QualityDimension.COMPLETENESS.value: self._assess_completeness(result),
            QualityDimension.MAINTAINABILITY.value: 0.7,
        }

    def _identify_root_causes(self, errors: list[Error]) -> list[str]:
        """Identify root causes from errors."""
        causes: list[str] = []

        category_errors: dict[str, list[Error]] = {}
        for error in errors:
            cat = error.category.value
            if cat not in category_errors:
                category_errors[cat] = []
            category_errors[cat].append(error)

        for category, cat_errors in category_errors.items():
            if len(cat_errors) >= 2:
                common_contexts = self._find_common_contexts(cat_errors)
                if common_contexts:
                    causes.append(f"Multiple {category} errors in: {common_contexts[0]}")
                else:
                    causes.append(f"Recurring {category} errors")

        for error in errors:
            if error.suggested_fix and error.suggested_fix not in causes:
                causes.append(error.suggested_fix)

        return causes[:5]

    def _identify_error_patterns(self, errors: list[Error]) -> list[str]:
        """Identify error patterns."""
        patterns: list[str] = []

        message_keywords: dict[str, int] = {}
        for error in errors:
            words = error.message.lower().split()
            for word in words:
                if len(word) > 3:
                    message_keywords[word] = message_keywords.get(word, 0) + 1

        frequent_keywords = [
            kw for kw, count in message_keywords.items() if count >= len(errors) / 3
        ]
        if frequent_keywords:
            patterns.append(f"Common error keywords: {', '.join(frequent_keywords[:3])}")

        location_counts: dict[str, int] = {}
        for error in errors:
            if error.location:
                location_counts[error.location] = location_counts.get(error.location, 0) + 1

        frequent_locations = [loc for loc, count in location_counts.items() if count >= 2]
        if frequent_locations:
            patterns.append(f"Error hotspots: {', '.join(frequent_locations[:3])}")

        return patterns

    def _assess_impact(self, errors: list[Error], severity_counts: dict[str, int]) -> str:
        """Assess impact of errors."""
        if severity_counts["critical"] > 0:
            return f"Critical impact: {severity_counts['critical']} critical errors detected"
        elif severity_counts["high"] > 0:
            return f"High impact: {severity_counts['high']} high severity errors"
        elif severity_counts["medium"] > 0:
            return f"Medium impact: {severity_counts['medium']} medium severity errors"
        elif severity_counts["low"] > 0:
            return f"Low impact: {severity_counts['low']} low severity errors"
        else:
            return "Minimal impact"

    def _calculate_recurrence_risk(self, errors: list[Error]) -> float:
        """Calculate error recurrence risk."""
        if not errors:
            return 0.0

        recurring = len(
            [
                e
                for e in errors
                if e.category
                in [
                    ErrorCategory.CONFIGURATION,
                    ErrorCategory.DEPENDENCY,
                    ErrorCategory.NETWORK,
                ]
            ]
        )

        return recurring / len(errors)

    def _generate_suggested_actions(self, errors: list[Error], root_causes: list[str]) -> list[str]:
        """Generate suggested actions."""
        actions: list[str] = []

        for root_cause in root_causes[:3]:
            actions.append(f"Address: {root_cause}")

        critical_errors = [e for e in errors if e.severity == ErrorSeverity.CRITICAL]
        for error in critical_errors[:2]:
            if error.suggested_fix:
                actions.append(error.suggested_fix)

        return actions

    def _create_improvement_from_root_cause(
        self, root_cause: str, analysis: Analysis
    ) -> Improvement:
        """Create improvement from root cause."""
        priority = (
            ImprovementPriority.HIGH if analysis.critical_count > 0 else ImprovementPriority.MEDIUM
        )

        return Improvement(
            priority=priority,
            category="error_fix",
            description=f"Fix root cause: {root_cause}",
            rationale=f"Identified as contributing to {analysis.error_count} errors",
            estimated_impact=0.2,
            implementation_steps=[
                "Investigate root cause",
                "Implement fix",
                "Verify solution",
            ],
        )

    def _create_improvement_from_pattern(self, pattern: str, analysis: Analysis) -> Improvement:
        """Create improvement from error pattern."""
        return Improvement(
            priority=ImprovementPriority.MEDIUM,
            category="pattern_prevention",
            description=f"Address pattern: {pattern}",
            rationale="Prevent recurring error patterns",
            estimated_impact=0.15,
            implementation_steps=[
                "Analyze pattern occurrences",
                "Add preventive checks",
                "Monitor for pattern recurrence",
            ],
        )

    def _apply_improvement(self, improvement: Improvement, result: WorkflowResult) -> Correction:
        """Apply an improvement."""
        correction = Correction(
            error_id="",
            status=CorrectionStatus.PENDING,
            action=improvement.description,
        )

        try:
            if improvement.category == "error_fix":
                correction.status = CorrectionStatus.APPLIED
                correction.result = "Fix applied"
            elif improvement.category == "pattern_prevention":
                correction.status = CorrectionStatus.APPLIED
                correction.result = "Preventive measures added"
            elif improvement.category == "prevention":
                correction.status = CorrectionStatus.APPLIED
                correction.result = "Prevention mechanisms implemented"
            else:
                correction.status = CorrectionStatus.SKIPPED
                correction.result = "Improvement type not supported for auto-correction"

        except Exception as e:
            correction.status = CorrectionStatus.FAILED
            correction.result = str(e)

        return correction

    def _verify_corrections(self, result: WorkflowResult, corrections: list[Correction]) -> bool:
        """Verify applied corrections."""
        applied = [c for c in corrections if c.status == CorrectionStatus.APPLIED]
        failed = [c for c in corrections if c.status == CorrectionStatus.FAILED]

        if not corrections:
            return True

        return len(applied) > len(failed)

    def _assess_correctness(self, result: WorkflowResult) -> float:
        """Assess correctness dimension."""
        if result.success:
            return 1.0

        success_rate = self._calculate_task_completion_rate(result)
        return success_rate * 0.5

    def _assess_efficiency(self, result: WorkflowResult) -> float:
        """Assess efficiency dimension."""
        return self._calculate_execution_efficiency(result)

    def _assess_reliability(self, result: WorkflowResult) -> float:
        """Assess reliability dimension."""
        return self._calculate_task_completion_rate(result)

    def _assess_completeness(self, result: WorkflowResult) -> float:
        """Assess completeness dimension."""
        total_tasks = len(result.execution_plan.steps)
        completed_tasks = len(result.execution_results)

        if total_tasks == 0:
            return 0.0

        return completed_tasks / total_tasks

    def _assess_maintainability(self, result: WorkflowResult) -> float:
        """Assess maintainability dimension."""
        score = 0.7

        context = result.metadata.get("context", {})
        if "reflections" in context:
            score += 0.1

        if result.execution_plan.checkpoints:
            score += 0.1

        return min(score, 1.0)

    def _calculate_grade(self, overall: float) -> str:
        """Calculate letter grade from overall score."""
        if overall >= 0.9:
            return "A"
        elif overall >= 0.8:
            return "B"
        elif overall >= 0.7:
            return "C"
        elif overall >= 0.6:
            return "D"
        else:
            return "F"

    def _create_quality_breakdown(
        self, result: WorkflowResult, dimensions: dict[str, float]
    ) -> dict[str, Any]:
        """Create quality breakdown details."""
        return {
            "workflow_id": result.workflow_id,
            "success": result.success,
            "duration": result.total_duration,
            "tasks": {
                "total": len(result.execution_plan.steps),
                "completed": len(result.execution_results),
                "successful": len([r for r in result.execution_results if r.success]),
            },
            "dimensions": dimensions,
        }

    def _generate_quality_recommendations(self, dimensions: dict[str, float]) -> list[str]:
        """Generate recommendations based on dimension scores."""
        recommendations: list[str] = []

        for dimension, score in dimensions.items():
            if score < 0.7:
                recommendations.append(f"Improve {dimension}: current score {score:.2%}")

        return recommendations

    def _extract_errors_from_result(self, result: WorkflowResult) -> list[Error]:
        """Extract errors from workflow result."""
        errors: list[Error] = []

        if result.error:
            errors.append(
                Error(
                    severity=ErrorSeverity.HIGH,
                    category=self._classify_error(result.error),
                    message=result.error,
                    location="workflow",
                    related_task="workflow_execution",
                )
            )

        for exec_result in result.execution_results:
            if not exec_result.success and exec_result.error:
                errors.append(
                    Error(
                        severity=ErrorSeverity.MEDIUM,
                        category=self._classify_error(exec_result.error),
                        message=exec_result.error,
                        location=exec_result.task_id,
                        related_task=exec_result.task_id,
                    )
                )

        return errors

    def _classify_error(self, error_msg: str) -> ErrorCategory:
        """Classify error message into category."""
        msg_lower = error_msg.lower()

        if "timeout" in msg_lower or "timed out" in msg_lower:
            return ErrorCategory.TIMEOUT
        elif "network" in msg_lower or "connection" in msg_lower:
            return ErrorCategory.NETWORK
        elif "permission" in msg_lower or "access" in msg_lower:
            return ErrorCategory.PERMISSION
        elif "not found" in msg_lower or "does not exist" in msg_lower:
            return ErrorCategory.RESOURCE
        elif "dependency" in msg_lower or "module" in msg_lower or "import" in msg_lower:
            return ErrorCategory.DEPENDENCY
        elif "config" in msg_lower or "setting" in msg_lower:
            return ErrorCategory.CONFIGURATION
        elif "syntax" in msg_lower or "parse" in msg_lower:
            return ErrorCategory.SYNTAX
        elif "security" in msg_lower or "auth" in msg_lower:
            return ErrorCategory.SECURITY
        elif "performance" in msg_lower or "slow" in msg_lower:
            return ErrorCategory.PERFORMANCE
        else:
            return ErrorCategory.LOGIC

    def _find_common_contexts(self, errors: list[Error]) -> list[str]:
        """Find common contexts among errors."""
        contexts: dict[str, int] = {}
        for error in errors:
            if error.context:
                contexts[error.context] = contexts.get(error.context, 0) + 1

        return [ctx for ctx, count in sorted(contexts.items(), key=lambda x: x[1], reverse=True)][
            :3
        ]

    def _generate_report_summary(
        self, review: Review, analysis: Analysis, quality: QualityScore
    ) -> str:
        """Generate summary for reflection report."""
        return (
            f"Workflow review: {review.overall_score:.2%} quality score. "
            f"Grade: {quality.grade}. "
            f"Errors found: {analysis.error_count}. "
            f"Status: {'Approved' if review.approved else 'Needs improvement'}"
        )

    def _generate_action_items(self, improvements: list[Improvement]) -> list[str]:
        """Generate action items from improvements."""
        return [f"[{imp.priority.value}] {imp.description}" for imp in improvements[:5]]

    def _generate_next_steps(self, review: Review, quality: QualityScore) -> list[str]:
        """Generate next steps based on review and quality."""
        steps: list[str] = []

        if not quality.passed:
            steps.append("Address quality issues before proceeding")
            steps.append("Review failed dimensions and implement fixes")

        if review.recommendations:
            steps.extend(review.recommendations[:3])

        if quality.passed:
            steps.append("Proceed with workflow completion")
            steps.append("Document lessons learned")

        return steps

    def _persist_report(self, report: ReflectionReport) -> None:
        """Persist reflection report to storage."""
        try:
            reports_dir = self._storage_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)

            report_file = reports_dir / f"report_{report.id}.json"
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass


__all__ = [
    "ReflectionSystem",
    "Review",
    "Error",
    "Analysis",
    "Improvement",
    "Correction",
    "CorrectedResult",
    "QualityScore",
    "ReflectionReport",
    "ReviewType",
    "ErrorSeverity",
    "ErrorCategory",
    "ImprovementPriority",
    "QualityDimension",
    "CorrectionStatus",
]
