# SOTA Code Ability Evaluation Report

**Date**: 2026-05-02  
**Model**: huihui_ai/qwen3.5-abliterated:0.8B (Ollama, 0.8B params, abused variant)  
**System**: OpenLaoKe v0.1.32 with Phase 0-3 multi-lang code engine

## Results Summary

| Mode | Pass Rate | Python | C | Rust |
|------|-----------|--------|---|------|
| Direct (no tools) | 1/7 (14%) | 0/4 (0%) | 0/2 (0%) | 1/1 (100%) |
| Tooled (CodeRunner) | 2/7 (28%) | 0/4 (0%) | 2/2 (100%) | 0/1 (0%) |

**Tooled mode doubled the pass rate (14% → 28%).**

## Per-Test Analysis

### Python (4 tests, all failed both modes)

| Test | Direct | Tooled | Root Cause |
|------|--------|--------|------------|
| Fibonacci | Code OK but wrapped in ``` markers | Refinement lost context | `_extract_code` fails on ```python block |
| List filter | Similar issue | Model forgets task | 0.8B model has poor multi-turn memory |
| Word freq | Incomplete output | Irrelevant refinement output | Model too small for medium difficulty |
| BST | Structure visible, incomplete | Generic "I'll help" response | Model cannot handle OOP tasks |

**Key issue**: Python `_extract_code` doesn't strip ```markers from inside the code string. The sandbox then executes ```python which is a syntax error.

### C (2 tests, both passed in tooled mode!)

| Test | Direct | Tooled | Root Cause |
|------|--------|--------|------------|
| Hello + sum | Keyword mismatch | Compilation succeeded! | clang compiled + ran the code |
| String reverse | Keyword mismatch | Compilation succeeded! | Same - compilation validates correctness |

**Key insight**: For C, the compiler acts as an automatic validator. The model tends to produce valid C syntax (likely due to training data). The tooled mode wins because it actually compiles and runs the code, discovering that it works even though keyword matching failed.

### Rust (1 test)

| Test | Direct | Tooled | Root Cause |
|------|--------|--------|------------|
| Vec sum | PERFECT output | Failed (no rustc) | Direct: model produced correct code. Tooled: cargo not in PATH |

The model produced EXACTLY the correct Rust code in direct mode. The tooled mode failed only because this machine lacks Rust toolchain, and the "rustc not found" error confused the model.

## Critical Issues Found

### 1. Python code extraction fails on ``` markers
The model wraps code in ```python blocks. `_extract_code` corrects tries to strip them via regex, but the model output sometimes includes the markers inside the extracted code string.

### 2. Iterative refinement fails for 0.8B models
The 0.8B model loses context after 1-2 additional turns. The refinement feedback is too complex for it to parse. For models this small, the refinement should:
- Be limited to 1 round
- Include the ORIGINAL problem description (not just error)
- Use simpler, more direct language

### 3. C compilation pipeline is the star performer
Despite being the smallest model, C code passes compilation + execution in tooled mode. The C compiler provides definitive binary feedback that the sandbox can validate. No keyword matching needed.

## Recommendations

### For 0.8B class models (immediate):
1. Fix `_extract_code` to handle ``` ```python ```c ```rust markers robustly
2. Limit refinement to 1 round max for tiny models
3. Always include original task description in refinement prompts
4. For Python: add automatic `import ast; ast.parse(code)` syntax check

### For 3B+ class models (next):
The same evaluation should be repeated with qwen2.5:3b or llama3.2:3b. Expected: Python tests will pass, refinement will work, C/Rust will maintain.

### For SOTA comparison (future):
1. Add GPT-4o / Claude Sonnet baseline for same tests
2. Measure: code correctness (exec pass), style (linter score), efficiency (runtime)
3. Track improvements per model size tier
