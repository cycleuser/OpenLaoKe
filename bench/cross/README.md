# Cross-Tool Benchmark

Compare OpenLaoKe against opencode, pi, and claude code on a shared task suite
with unified file-level verification.

## Quick start

```bash
# Run OpenLaoKe + opencode over smoke + polyglot suites
python -m bench.cross.run --tools openlaoke,opencode --suites smoke,polyglot --timeout 120

# Add pi (needs a configured provider)
python -m bench.cross.run --tools openlaoke,opencode,pi --suites smoke,polyglot,tooluse

# Compare results from one or more runs
python -m bench.cross.compare bench/cross/results/<run>.json
python -m bench.cross.compare bench/cross/results/a.json bench/cross/results/b.json
```

## How it works

1. **Same tasks**: reuses `bench/harness.py` task suites (smoke/polyglot/tooluse).
2. **Same verifier**: `TaskVerifier` inspects the filesystem — no trust in agent
   self-reported success.
3. **Isolated sandboxes**: each `(tool, task)` runs in its own temp directory;
   setup files are pre-seeded, then the agent's headless mode is invoked.
4. **Hard timeout**: a stuck agent is killed and scored as a failure.
5. **Comparable scorecard**: pass count, partial score, mean duration.

## Tool adapters

Each adapter translates `(prompt, work_dir)` into the tool's headless command:

| tool       | command                                          |
|------------|--------------------------------------------------|
| openlaoke  | `python -m openlaoke -c <dir> <prompt>`          |
| opencode   | `opencode run --dir <dir> <prompt>`              |
| pi         | `pi --print -p <prompt> --no-session`            |
| claude     | `claude -p <prompt> --cwd <dir>`                 |

## Prerequisites

- **openlaoke**: configure a provider in `~/.openlaoke/config.json` and set
  `auto_approve_all: true` for headless tool execution.
- **opencode**: run `opencode auth` once; the harness reuses its credentials.
- **pi**: set a provider API key env var (e.g. `GOOGLE_API_KEY`).
- **claude**: install `claude` CLI and authenticate.

## Reading the report

```
task                            openlaoke     opencode
poly-py-class                       PASS         fail
poly-js-function                    fail         fail
...
WIN count                               2            2
TIES                                   17
```

- **PASS/fail**: whether the task's file-level verification passed.
- **WIN count**: tasks where only that tool passed (others failed).
- **TIES**: tasks where all tools passed (or all failed).
- **score**: mean partial score across all tasks (accounts for partially-met
  verification criteria, e.g. file exists but content doesn't fully match).

## Fairness notes

- All tools should use comparable models for a fair comparison. The harness
  does not enforce model parity — set it per-tool before running.
- Wall-clock times include tool startup overhead; use them for relative
  comparison, not absolute performance claims.
- Tasks are simple file-creation/editing operations; they exercise tool-calling
  reliability, not deep reasoning. Add harder suites to `bench/harness.py` for
  broader coverage.