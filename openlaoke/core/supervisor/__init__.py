"""Task supervision system - ensures tasks are completed."""

from __future__ import annotations

from openlaoke.core.supervisor.checker import TaskCompletionChecker
from openlaoke.core.supervisor.context_hygiene import WriteBuffer, extract_key_quotes
from openlaoke.core.supervisor.lab_notebook import LabEntry, LabNotebook
from openlaoke.core.supervisor.provenance import (
    ConfidenceLevel,
    ProvenanceRecord,
    SourceEntry,
    SourceType,
    VerificationCheck,
    VerificationStatus,
)
from openlaoke.core.supervisor.requirements import TaskRequirements
from openlaoke.core.supervisor.slug_utils import (
    ensure_output_dirs,
    generate_slug,
    get_output_paths,
    validate_slug,
)
from openlaoke.core.supervisor.supervisor import (
    RetryReason,
    SupervisedTask,
    SupervisionResult,
    TaskStatus,
    TaskSupervisor,
)

__all__ = [
    "TaskSupervisor",
    "TaskCompletionChecker",
    "TaskRequirements",
    "SupervisedTask",
    "SupervisionResult",
    "TaskStatus",
    "RetryReason",
    "ProvenanceRecord",
    "SourceEntry",
    "VerificationCheck",
    "VerificationStatus",
    "SourceType",
    "ConfidenceLevel",
    "generate_slug",
    "get_output_paths",
    "ensure_output_dirs",
    "validate_slug",
    "LabNotebook",
    "LabEntry",
    "WriteBuffer",
    "extract_key_quotes",
]
