"""Contract tools for definition-of-done assertions.

Tools: contract_create, contract_assert_pass, contract_assert_fail,
contract_assert_skip, contract_status.
"""

from __future__ import annotations

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

        store = ContractStore()
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


class ContractAssertPassTool(Tool):
    name = "ContractAssertPass"
    description = "Mark an assertion as passed with command-line evidence"
    input_schema = ContractAssertArgs
    is_read_only = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        contract_id = str(kwargs.get("contract_id", ""))
        assertion_id = str(kwargs.get("assertion_id", ""))
        evidence = str(kwargs.get("evidence", ""))

        store = ContractStore()
        contract = store.load(contract_id)
        if not contract:
            return ToolResultBlock(result_for_assistant=f"Contract {contract_id} not found")

        for a in contract.assertions:
            if str(a.id) == assertion_id:
                a.state = "passed"
                a.evidence = evidence
                store.save(contract)
                return ToolResultBlock(
                    result_for_assistant=f"[OK] Assertion {assertion_id} marked passed: {a.description}"
                )

        return ToolResultBlock(
            result_for_assistant=f"Assertion {assertion_id} not found in contract {contract_id}"
        )


class ContractAssertFailTool(Tool):
    name = "ContractAssertFail"
    description = "Mark an assertion as failed with evidence"
    input_schema = ContractAssertArgs
    is_read_only = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        contract_id = str(kwargs.get("contract_id", ""))
        assertion_id = str(kwargs.get("assertion_id", ""))
        evidence = str(kwargs.get("evidence", ""))

        store = ContractStore()
        contract = store.load(contract_id)
        if not contract:
            return ToolResultBlock(result_for_assistant=f"Contract {contract_id} not found")

        for a in contract.assertions:
            if str(a.id) == assertion_id:
                a.state = "failed"
                a.evidence = evidence
                store.save(contract)
                return ToolResultBlock(
                    result_for_assistant=f"[FAIL] Assertion {assertion_id} marked failed: {a.description}"
                )

        return ToolResultBlock(
            result_for_assistant=f"Assertion {assertion_id} not found in contract {contract_id}"
        )


class ContractAssertSkipTool(Tool):
    name = "ContractAssertSkip"
    description = "Mark an assertion as skipped (out of scope)"
    input_schema = ContractAssertArgs
    is_read_only = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        contract_id = str(kwargs.get("contract_id", ""))
        assertion_id = str(kwargs.get("assertion_id", ""))
        evidence = str(kwargs.get("evidence", ""))

        store = ContractStore()
        contract = store.load(contract_id)
        if not contract:
            return ToolResultBlock(result_for_assistant=f"Contract {contract_id} not found")

        for a in contract.assertions:
            if str(a.id) == assertion_id:
                a.state = "skipped"
                a.evidence = evidence
                store.save(contract)
                return ToolResultBlock(
                    result_for_assistant=f"[SKIP] Assertion {assertion_id} marked skipped: {a.description}"
                )

        return ToolResultBlock(
            result_for_assistant=f"Assertion {assertion_id} not found in contract {contract_id}"
        )


class ContractStatusTool(Tool):
    name = "ContractStatus"
    description = "Show the active contract: assertions, states, blockers"
    input_schema = ContractStatusArgs
    is_read_only = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        contract_id = str(kwargs.get("contract_id", ""))

        store = ContractStore()
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
