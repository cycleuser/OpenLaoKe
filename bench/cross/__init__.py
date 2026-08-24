"""Cross-tool comparison harness: OpenLaoKe vs opencode vs pi (vs claude code).

Runs the same task suite against multiple AI coding agents in isolated
sandbox directories and verifies results with a unified file-level checker
(no trust in agent self-reporting).

Usage:
    python -m bench.cross.run --tools openlaoke,opencode,pi
    python -m bench.cross.run --tools openlaoke --suites smoke,polyglot
    python -m bench.cross.run --compare bench/cross/results/a.json bench/cross/results/b.json

Each tool runs in its own temp directory; the harness pre-seeds setup files,
invokes the agent's headless mode, then verifies the produced files.
"""

from __future__ import annotations
