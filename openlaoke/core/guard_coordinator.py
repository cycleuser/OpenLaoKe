"""Unified guard coordinator.

Wraps multiple guard systems into a single coordinator for the agent loop:
routing, quality, deduplication, trust decay, early stop, read tracker,
contract guard, multi-file edit, snapshot manager, and evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from openlaoke.core.adaptive_temp import AdaptiveTemperature
from openlaoke.core.bootstrap import ProjectBootstrap, detect_bootstrap
from openlaoke.core.contract import ContractGuard, ContractStore
from openlaoke.core.early_stop import EarlyStopDetector, EarlyStopResult
from openlaoke.core.error_diagnosis import ErrorDiagnoser, ErrorDiagnosis
from openlaoke.core.escalation import EscalationEngine
from openlaoke.core.evidence import EvidenceStore
from openlaoke.core.knowledge_loader import KnowledgeLoader
from openlaoke.core.multi_file_edit import MultiFileEditCoordinator
from openlaoke.core.prompt_cache_split import PromptCacheSplit
from openlaoke.core.quality_monitor import QualityMonitor
from openlaoke.core.read_tracker import ReadTracker
from openlaoke.core.snapshot import SnapshotManager
from openlaoke.core.test_runner_discovery import TestRunnerInfo, detect_test_runner
from openlaoke.core.thinking_budget import ThinkingBudget
from openlaoke.core.tool_call_parser import extract_tool_calls
from openlaoke.core.tool_dedup import ToolCallCache
from openlaoke.core.tool_router import ToolRouter
from openlaoke.core.trust_decay import TrustDecay


@dataclass
class GuardCoordinator:
    tool_router: ToolRouter = field(default_factory=ToolRouter)
    quality_monitor: QualityMonitor = field(default_factory=QualityMonitor)
    dedup_cache: ToolCallCache = field(default_factory=ToolCallCache)
    trust_decay: TrustDecay = field(default_factory=TrustDecay)
    early_stop: EarlyStopDetector = field(default_factory=EarlyStopDetector)
    read_tracker: ReadTracker = field(default_factory=ReadTracker)
    contract_guard: ContractGuard = field(default_factory=ContractGuard)
    contract_store: ContractStore = field(default_factory=ContractStore)
    multi_file_edit: MultiFileEditCoordinator = field(default_factory=MultiFileEditCoordinator)
    snapshot_manager: SnapshotManager = field(default_factory=SnapshotManager)
    evidence_store: EvidenceStore = field(default_factory=EvidenceStore)
    error_diagnoser: ErrorDiagnoser = field(default_factory=ErrorDiagnoser)
    adaptive_temp: AdaptiveTemperature = field(default_factory=AdaptiveTemperature)
    thinking_budget: ThinkingBudget = field(default_factory=ThinkingBudget)
    knowledge_loader: KnowledgeLoader = field(default_factory=KnowledgeLoader)
    escalation_engine: EscalationEngine = field(default_factory=EscalationEngine)
    cache_split: PromptCacheSplit = field(default_factory=PromptCacheSplit)
    bootstrap: ProjectBootstrap | None = None
    test_runner: TestRunnerInfo | None = None

    known_tools: set[str] = field(default_factory=set)

    def route_tools(self, message: str) -> list[str]:
        result = self.tool_router.route(message)
        tools = result.tools or []
        all_tools = self.known_tools or set()
        filtered = [t for t in tools if t in all_tools]
        return filtered

    def parse_tool_calls(self, content: str, reasoning: str | None = None) -> list[dict]:
        return extract_tool_calls(content, self.known_tools, reasoning)

    def check_quality(self, content: str, tool_calls: list[dict]) -> str | None:
        r = self.quality_monitor.check(content, tool_calls, self.known_tools)
        return r.message if r.has_issue else None

    def check_dedup(self, tool_name: str, args: dict) -> str | None:
        return self.dedup_cache.check(tool_name, args)

    def check_idempotent_write_dedup(self, tool_name: str, args: dict) -> str | None:
        return self.dedup_cache.check_idempotent_write(tool_name, args)

    def record_tool_result(self, tool_name: str, args: dict, result: str) -> None:
        self.dedup_cache.record(tool_name, args, result)

    def record_tool_success(self, tool_name: str) -> None:
        self.trust_decay.record_success(tool_name)

    def record_tool_failure(self, tool_name: str) -> None:
        self.trust_decay.record_failure(tool_name)

    def filter_schemas(self, schemas: list[dict]) -> list[dict]:
        return self.trust_decay.filter_tool_schemas(schemas)

    def check_early_stop_detailed(
        self, output: str, tool_name: str = "", file_path: str = "", success: bool = True
    ) -> EarlyStopResult:
        r = self.early_stop.detect_repetition(output)
        if r.should_stop:
            return r
        r = self.early_stop.detect_greeting_regression(output)
        if r.should_stop:
            return r
        if tool_name:
            r = self.early_stop.detect_read_loop(tool_name)
            if r.should_stop:
                return r
        if tool_name in ("Edit", "ApplyPatch") and file_path:
            r = self.early_stop.detect_patch_spiral(tool_name, file_path, success)
            if r.should_stop:
                return r
        return EarlyStopResult()

    def check_write_guard(self, path: str) -> str | None:
        return self.read_tracker.check_before_write(path)

    def check_contract_done(self, output: str) -> str | None:
        active = self.contract_store.load_active()
        return self.contract_guard.check_done_claim(output, active)

    def diagnose_error(self, command: str, stderr: str, exit_code: int) -> ErrorDiagnosis:
        return self.error_diagnoser.diagnose(command, stderr, exit_code, "")

    def detect_project(self, work_dir: str = "") -> None:
        self.bootstrap = detect_bootstrap(work_dir)
        self.test_runner = detect_test_runner(work_dir)

    def reset_turn(self) -> None:
        self.dedup_cache.reset_turn()
        self.multi_file_edit.reset_turn()
        self.snapshot_manager.commit()

    def get_bootstrap_summary(self) -> str:
        if self.bootstrap:
            return self.bootstrap.to_summary()
        return ""

    def get_test_command(self) -> str:
        if self.test_runner:
            return self.test_runner.command
        return ""
