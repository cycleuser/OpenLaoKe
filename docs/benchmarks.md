# Benchmarks: Provider Formats, Local Models, and Harness Comparison

This document records the verification and comparison runs used to validate
OpenLaoKe's provider layer and to compare OpenLaoKe against
[pi](https://github.com/earendil-works/pi) as a harness, using local Ollama
models across ten languages.

All results were produced on one machine and are reproduced here with enough
detail to re-run them. Numbers from small models are noisy; treat them as
directional, not authoritative.

## Environment

| Item | Value |
|------|-------|
| Machine | macOS (Apple Silicon), local |
| Python | 3.12 (conda env `dev`) |
| OpenLaoKe | 0.1.40 |
| pi | 0.85.1 |
| Ollama | 0.34.2, serving on `http://127.0.0.1:11434` |
| Local endpoint | `http://127.0.0.1:11434/v1` (OpenAI-compatible) |

Chat-capable models tested (Ollama). The Params/Quant/Capabilities columns are
taken from `ollama show`:

| Model | Params | Quant | Capabilities |
|-------|-------:|-------|--------------|
| `qwen3.5:2b` | 2.3B | Q8_0 | completion, vision, tools, thinking |
| `qwen3.5:0.8b` | 873.44M | Q8_0 | completion, vision, tools, thinking |
| `LiquidAI-dev/lfm2.5-2.6b:latest` | 2.7B | Q4_K_M | completion, tools, thinking |
| `LiquidAI/lfm2.5-350m:latest` | 354.48M | Q8_0 | completion, tools, thinking |
| `lfm2.5-thinking:latest` | 1.2B | Q4_K_M | completion, tools, thinking |
| `granite4:350m-h` | 340.33M | Q8_0 | completion, tools |

All six models appear in the results below. For day-to-day use the local set was
later trimmed to the two models at or above 2B (`qwen3.5:2b`,
`LiquidAI-dev/lfm2.5-2.6b`); the data for the removed models is kept here.

> **Note.** A thinking model must be given enough `max_tokens`; otherwise the
> entire budget is spent on reasoning and the visible answer is empty. We used
> `max_tokens=1200` for the language runs and `2000` for tool runs.

## Part 1 — Provider format compatibility

OpenLaoKe must speak both the OpenAI and the Anthropic (Claude) formats. Both
were exercised end to end.

| Test | Endpoint | Result |
|------|----------|--------|
| OpenAI format, non-stream | `POST https://api.deepseek.com/v1/chat/completions` | ✅ returned `PONG` |
| OpenAI format, streaming | same | ✅ streamed `PONG` |
| Anthropic format, real endpoint | `POST https://api.anthropic.com/v1/messages` (invalid key) | ✅ correct request; standard 401 `authentication_error` |
| Anthropic format, full request/response | local mock | ✅ PASS |
| Local OpenAI-compatible | `POST http://127.0.0.1:11434/v1/chat/completions` | ✅ returned `PONG` |

The Anthropic mock verified the exact contract, not just connectivity:

- path `/v1/messages`
- header `anthropic-version: 2023-06-01`
- header `x-api-key`
- body keys `model`, `messages`, `max_tokens`, `temperature`, `system`
- response parsing: `content[0].text == "PONG"`, usage `input=11, output=2`

Local endpoints no longer require an API key: when the base URL is a local
address (`localhost`, `127.0.0.1`, `0.0.0.0`, `::1`, `host.docker.internal`)
and no key is configured, OpenLaoKe sends a placeholder bearer token.

## Part 2 — Local model capabilities (OpenLaoKe)

Each chat model was driven through OpenLaoKe's OpenAI-compatible client with a
trivial prompt, then through the full agent loop with a file-writing task
("create `out.txt` containing `hello pi`, then run `cat out.txt`").

| Model | Plain | Streaming | Tool calling | Notes |
|-------|:-----:|:---------:|:------------:|-------|
| `qwen3.5:2b` | ✅ | ✅ | ✅ | best overall |
| `qwen3.5:0.8b` | ✅ | ✅ | ✅ | wrote `hello pi.` (extra period) |
| `LiquidAI-dev/lfm2.5-2.6b` | ✅ | ✅ | ✅ | wrote `hello pi.` (extra period) |
| `LiquidAI/lfm2.5-350m` | ✅ | ✅ | ✅ | correct file content |
| `lfm2.5-thinking` | ✅ | ✅ | ❌ | thinks instead of acting |
| `granite4:350m-h` | ✅ | ✅ | ❌ | hallucinated tool errors |

Embedding-only models (`nomic-embed-text`, `snowflake-arctic-embed`,
`all-minilm` ×2, `granite-embedding`) were correctly rejected with HTTP 400 on
`/chat/completions`; they are not chat models and are excluded from the tables
below.

**Bug found and fixed during Part 2.** Ollama's OpenAI-compatible stream places
reasoning in `delta.reasoning`, while DeepSeek uses `delta.reasoning_content`.
OpenLaoKe originally read only the latter, so thinking models produced an empty
stream. Both fields are now read.

## Part 3 — Multilingual fidelity: OpenLaoKe vs pi

Each harness was asked, in ten languages, to "introduce yourself in one
sentence". The reply was classified by script (Hangul → Korean; kana →
Japanese; CJK → Chinese; Cyrillic → Russian) and, for Latin scripts, by
stopword signatures. `OK` means the detected language matched the request.

### Setup

- **OpenLaoKe:**
  `python -m openlaoke --provider openai_compatible --base-url http://127.0.0.1:11434/v1 --api-key not-needed --model <m> --max-tokens 1200 "<prompt>"`
- **pi:** `~/.pi/agent/models.json` declares an `ollama-local` provider
  (`api: openai-completions`, `compat.supportsDeveloperRole=false`,
  `compat.supportsReasoningEffort=false`); run as
  `pi -p --provider ollama-local --model <m> --no-skills --no-context-files --no-extensions --no-prompt-templates --no-themes "<prompt>"`

### OpenLaoKe

| Model | zh | en | ja | fr | ru | de | es | pt | it | ko | Score |
|-------|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|------:|
| `qwen3.5:2b` | OK | OK | OK | OK | OK | OK | OK | OK | OK | OK | 10/10 |
| `qwen3.5:0.8b` | OK | OK | OK | OK | OK | zh | OK | OK | OK | en | 8/10 |
| `LiquidAI-dev/lfm2.5-2.6b` | OK | OK | OK | OK | en | OK | OK | OK | OK | OK | 9/10 |
| `LiquidAI/lfm2.5-350m` | en | OK | OK | OK | OK | OK | OK | OK | es | OK | 8/10 |
| `lfm2.5-thinking` | en | OK | OK | OK | en | en | OK | en | en | OK | 5/10 |
| `granite4:350m-h` | empty | OK | en | ? | en | en | en | OK | en | en | 2/10 |

### pi

| Model | zh | en | ja | fr | ru | de | es | pt | it | ko | Score |
|-------|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|------:|
| `qwen3.5:2b` | OK | OK | OK | OK | OK | OK | OK | OK | es | OK | 9/10 |
| `qwen3.5:0.8b` | empty | OK | OK | OK | OK | OK | OK | OK | OK | OK | 9/10 |
| `LiquidAI-dev/lfm2.5-2.6b` | OK | OK | zh | OK | OK | OK | OK | es | OK | OK | 8/10 |
| `LiquidAI/lfm2.5-350m` | OK | OK | OK | OK | OK | OK | OK | en | OK | OK | 9/10 |
| `lfm2.5-thinking` | en | OK | en | en | OK | en | OK | en | en | en | 3/10 |
| `granite4:350m-h` | en | OK | en | OK | en | en | en | OK | es | en | 3/10 |

### Totals

| Harness | Passed |
|---------|-------:|
| OpenLaoKe | **42/60** |
| pi | 41/60 |

Passes per language (both harnesses combined, out of 12):

| Language | Passes | Language | Passes |
|----------|-------:|----------|-------:|
| en | 12/12 | pt | 8/12 |
| fr | 10/12 | ko | 8/12 |
| es | 10/12 | de | 7/12 |
| ja | 8/12 | zh | 6/12 |
| ru | 8/12 | it | 6/12 |

## Findings

1. **The harness is not the bottleneck.** OpenLaoKe (42/60) and pi (41/60) are
   effectively tied; the difference is within model noise. The same model
   behaves nearly the same in both harnesses.
2. **Model choice dominates.** `qwen3.5:2b` scored 10/10 and 9/10 across the two
   harnesses; `granite4:350m-h` and `lfm2.5-thinking` scored 2–5/10 in both.
3. **The harness shapes identity, not language.** The same model answers
   "I am OpenLaoKe…" under OpenLaoKe and "I am Pi Coding Agent…" under pi,
   confirming the harness system prompt is applied — without changing the
   response language.
4. **Very small models are unsuitable for agent work.** `granite4:350m-h` under
   OpenLaoKe hallucinated tool use and created files; the harness plumbing was
   correct, the model was not.

## Caveats

- The language classifier is heuristic. `?`, `es`, `zh` etc. can indicate a
  mixed-language reply or a classifier boundary rather than a hard failure.
- One run per cell. Small models are nondeterministic; re-runs will move
  individual cells.
- Two anomalies: `pi + qwen3.5:0.8b + zh` timed out at 420 s (empty);
  `openlaoke + granite4:350m-h + zh` returned empty.
- `en` is the strongest language for every model; `zh`/`it` the weakest. This is
  a property of the models, not of either harness.

## Reproducing

```bash
# 1. Provider formats (needs a DeepSeek key for the OpenAI path; the Anthropic
#    path is validated against a local mock)
python scripts/bench_provider_formats.py

# 2. Local model capabilities and tool calling
python scripts/bench_local_models.py --base-url http://127.0.0.1:11434/v1

# 3. Multilingual, both harnesses
python scripts/bench_harness_multilang.py
```

See the scripts in `scripts/` for the exact model lists, prompts and language
classifier.
