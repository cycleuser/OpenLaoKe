"""Snapshot-based rewind, fork, branch, summarize-from/up-to.

A snapshot captures the *first-touch content* of each file touched in a
turn. Rewinding restores that content. Forks write a new session that
contains the messages up to the fork point plus a sidecar ``.meta`` file
with the lineage.
"""

from __future__ import annotations
