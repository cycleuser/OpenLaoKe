"""Language specification definitions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LanguageSpec:
    name: str
    display_name: str
    extensions: list[str] = field(default_factory=list)
    compiler: str | None = None
    interpreter: str | None = None
    test_runner: str | None = None
    static_analyzers: list[str] = field(default_factory=list)
    sandbox_kind: str = "subprocess"
    allowed_ops: dict[str, bool] = field(default_factory=dict)
    default_timeout_ms: int = 30000
    default_mem_mb: int = 256


PYTHON_SPEC = LanguageSpec(
    name="python",
    display_name="Python",
    extensions=[".py", ".pyi"],
    interpreter="python3",
    test_runner="pytest",
    static_analyzers=["mypy", "ruff", "pylint"],
    sandbox_kind="subprocess",
    allowed_ops={"file_read": True, "file_write": True, "network": False},
    default_timeout_ms=30000,
    default_mem_mb=256,
)

C_SPEC = LanguageSpec(
    name="c",
    display_name="C",
    extensions=[".c", ".h"],
    compiler="clang",
    test_runner="ctest",
    static_analyzers=["clang-tidy", "cppcheck"],
    sandbox_kind="subprocess",
    allowed_ops={"file_read": True, "file_write": True, "network": False},
    default_timeout_ms=30000,
    default_mem_mb=256,
)

RUST_SPEC = LanguageSpec(
    name="rust",
    display_name="Rust",
    extensions=[".rs"],
    compiler="rustc",
    test_runner="cargo test",
    static_analyzers=["rust-analyzer", "clippy"],
    sandbox_kind="subprocess",
    allowed_ops={"file_read": True, "file_write": True, "network": False},
    default_timeout_ms=60000,
    default_mem_mb=512,
)

DEFAULT_SPECS: list[LanguageSpec] = [PYTHON_SPEC, C_SPEC, RUST_SPEC]
