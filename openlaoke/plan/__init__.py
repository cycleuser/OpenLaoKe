"""Plan Mode: read-only gate + evidence ledger + auto-plan heuristic.

Plan mode is a *runtime read-only gate*, not a prompt toggle. The system
prompt, tool list, and message history never change when entering or
leaving plan mode. The gate is consulted at execute time and returns a
``blocked`` result the model adapts to.

After plan approval, the plan is the go-ahead. ``complete_step`` is a
read-only tool that records host-observed evidence per sub-step. The
final-answer readiness check refuses to accept a "done" answer if any
required evidence is missing.
"""

from __future__ import annotations
