"""Permission gate and approver.

The Gate is the single place every tool execution consults. It is
transport-agnostic: the :class:`Approver` decides whether to prompt the
user (interactive) or auto-allow (headless).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from openlaoke.permission.policy import Decision, Policy, is_readonly_bash_subject

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    decision: Decision
    reason: str = ""
    ticket_id: str = ""


Approver = Callable[[str, dict[str, Any]], Awaitable[Decision]]


class AutoAllowApprover:
    """Always allow (used for non-interactive runs)."""

    async def __call__(self, tool_name: str, tool_args: dict[str, Any]) -> Decision:
        return Decision.ALLOW


class Gate:
    """Consults the policy, classifies, and delegates to an approver."""

    def __init__(
        self,
        policy: Policy | None = None,
        approver: Approver | None = None,
        bypass: bool = False,
        tool_read_only_hint: Callable[[str], bool] | None = None,
    ) -> None:
        self.policy = policy or Policy()
        self.approver: Approver = approver or AutoAllowApprover()
        self.bypass = bypass
        self._ticket_seq = 0
        self._read_only_hint = tool_read_only_hint or (lambda name: False)

    def classify(self, tool_name: str, tool_args: dict[str, Any]) -> Decision:
        """Pure policy lookup. Does not consult the approver.

        Resolution order: deny rules > bypass > read-only hint > safe bash > allow rules > fallback.
        Deny rules are checked first so even read-only tools can be hard-blocked.
        """
        if self.bypass:
            return Decision.ALLOW
        # Check deny rules first — they always win.
        deny_decision = self.policy._match_rules(tool_name, tool_args, Decision.DENY)
        if deny_decision == Decision.DENY:
            return Decision.DENY
        # Read-only tools always allow (unless denied above).
        if self._read_only_hint(tool_name):
            return Decision.ALLOW
        if tool_name == "bash" and is_readonly_bash_subject(tool_args.get("command", "")):
            return Decision.ALLOW
        # Check explicit allow rules.
        allow_decision = self.policy._match_rules(tool_name, tool_args, Decision.ALLOW)
        if allow_decision == Decision.ALLOW:
            return Decision.ALLOW
        # Check explicit ask rules.
        ask_decision = self.policy._match_rules(tool_name, tool_args, Decision.ASK)
        if ask_decision == Decision.ASK:
            return Decision.ASK
        return self.policy._fallback(tool_name)

    async def check(self, tool_name: str, tool_args: dict[str, Any]) -> GateResult:
        """Classify and, if ASK, delegate to the approver."""
        decision = self.classify(tool_name, tool_args)
        if decision == Decision.DENY:
            return GateResult(decision, reason="denied by policy")
        if decision == Decision.ASK:
            chosen = await self.approver(tool_name, tool_args)
            return GateResult(chosen, reason="approver decided")
        return GateResult(Decision.ALLOW, reason="allowed by policy")

    def next_ticket_id(self) -> str:
        self._ticket_seq += 1
        return f"tkt_{self._ticket_seq}"
