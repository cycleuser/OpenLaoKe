"""Contract tools for definition-of-done assertions.

Tools: contract_create, contract_assert_pass, contract_assert_fail,
contract_assert_skip, contract_status.
"""

from __future__ import annotations

import os
import time
from typing import Any

from pydantic import BaseModel

from openlaoke.core.contract import (
    Assertion,
    Contract,
    ContractStore,
)
from openlaoke.core.tool import Tool, ToolContext
from openlaoke.types.core_types import ToolResultBlock

ASSERTION_STATES = {
    "passed": ("OK", "passed"),
    "failed": ("FAIL", "failed"),
    "skipped": ("SKIP", "skipped"),
}


def _get_store(ctx: ToolContext) -> ContractStore:
    base_dir = os.path.join(ctx.app_state.get_cwd(), ".openlaoke", "contracts")
    return ContractStore(base_dir=base_dir)


class ContractCreateArgs(BaseModel):
    description: str
    assertions: list[dict[str, Any]]


class ContractAssertArgs(BaseModel):
    contract_id: str
    assertion_id: str
    evidence: str = ""


class ContractStatusArgs(BaseModel):
    contract_id: str = ""


class ContractCreateTool(Tool):
    name = "ContractCreate"
    description = "Declare a Definition-of-Done contract with a list of testable assertions"
    input_schema = ContractCreateArgs
    is_read_only = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        description = str(kwargs.get("description", ""))
        assertions_raw = kwargs.get("assertions", [])

        store = _get_store(ctx)
        contract_id = str(int(time.time() * 1000))
        assertions = []
        for i, a in enumerate(assertions_raw):
            assertions.append(
                Assertion(
                    id=str(i + 1),
                    description=a.get("description", str(a)),
                )
            )

        contract = Contract(
            id=contract_id,
            description=description,
            work_dir=ctx.app_state.get_cwd(),
            assertions=assertions,
        )
        store.save(contract)

        lines = [
            f"Contract created: {contract_id}",
            f"Description: {description}",
            f"Assertions ({len(assertions)}):",
        ]
        for a in assertions:
            lines.append(f"  [{a.state}] {a.id}: {a.description}")

        return ToolResultBlock(result_for_assistant="\n".join(lines))


class _ContractAssertTool(Tool):
    is_read_only = False

    def _update_assertion(
        self, ctx: ToolContext, kwargs: dict[str, Any], new_state: str, icon: str
    ) -> ToolResultBlock:
        contract_id = str(kwargs.get("contract_id", ""))
        assertion_id = str(kwargs.get("assertion_id", ""))
        evidence = str(kwargs.get("evidence", ""))

        store = _get_store(ctx)
        contract = store.load(contract_id)
        if not contract:
            return ToolResultBlock(result_for_assistant=f"Contract {contract_id} not found")

        for a in contract.assertions:
            if str(a.id) == assertion_id:
                a.state = new_state
                a.evidence = evidence
                store.save(contract)
                return ToolResultBlock(
                    result_for_assistant=f"[{icon}] Assertion {assertion_id} marked {new_state}: {a.description}"
                )

        return ToolResultBlock(
            result_for_assistant=f"Assertion {assertion_id} not found in contract {contract_id}"
        )


class ContractAssertPassTool(_ContractAssertTool):
    name = "ContractAssertPass"
    description = "Mark an assertion as passed with command-line evidence"
    input_schema = ContractAssertArgs

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        return self._update_assertion(ctx, kwargs, "passed", "OK")


class ContractAssertFailTool(_ContractAssertTool):
    name = "ContractAssertFail"
    description = "Mark an assertion as failed with evidence"
    input_schema = ContractAssertArgs

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        return self._update_assertion(ctx, kwargs, "failed", "FAIL")


class ContractAssertSkipTool(_ContractAssertTool):
    name = "ContractAssertSkip"
    description = "Mark an assertion as skipped (out of scope)"
    input_schema = ContractAssertArgs

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        return self._update_assertion(ctx, kwargs, "skipped", "SKIP")


class ContractStatusTool(Tool):
    name = "ContractStatus"
    description = "Show the active contract: assertions, states, blockers"
    input_schema = ContractStatusArgs
    is_read_only = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        contract_id = str(kwargs.get("contract_id", ""))

        store = _get_store(ctx)
        if contract_id:
            contract = store.load(contract_id)
            if not contract:
                return ToolResultBlock(result_for_assistant=f"Contract {contract_id} not found")
            return ToolResultBlock(result_for_assistant=_format_contract(contract))

        contracts = store.load_active()
        if not contracts:
            return ToolResultBlock(result_for_assistant="No active contracts")

        lines = [f"Active contracts ({len(contracts)}):"]
        for c in contracts:
            lines.append(_format_contract(c))
            lines.append("")
        return ToolResultBlock(result_for_assistant="\n".join(lines))


def _format_contract(contract: Contract) -> str:
    done = " [DONE]" if contract.is_done else ""
    lines = [f"Contract: {contract.id}{done} - {contract.description}"]
    lines.append(f"State: {contract.state}")
    for a in contract.assertions:
        icon = {
            "passed": "PASS",
            "failed": "FAIL",
            "skipped": "SKIP",
            "pending": "PEND",
        }.get(a.state, a.state)
        lines.append(f"  [{icon}] {a.id}: {a.description}")
    return "\n".join(lines)
