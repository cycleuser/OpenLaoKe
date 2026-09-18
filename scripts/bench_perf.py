"""Speed benchmark for local models via Ollama's native API.

Measures, per model and prompt size:
  - prefill speed  = prompt_eval_count / prompt_eval_duration
  - decode speed   = eval_count / eval_duration
  - TTFT           (time to first streamed token)
  - total duration, model load duration

Usage:
    python /tmp/bench_perf.py
"""

from __future__ import annotations

import json
import statistics
import time
import urllib.request

HOST = "http://127.0.0.1:11434"
MODELS = ["qwen3.5:2b", "LiquidAI-dev/lfm2.5-2.6b:latest"]
REPEATS = 3
NUM_PREDICT = 128

FILLER = "The quick brown fox jumps over the lazy dog. "
SIZES = {
    "short(~15)": "用一句话介绍你自己。",
    "medium(~500)": FILLER * 55,
    "long(~2000)": FILLER * 220,
}


def post(path: str, payload: dict):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{HOST}{path}", data=data, headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=600)


def gen_once(model: str, prompt: str) -> dict:
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": NUM_PREDICT, "temperature": 0.0},
    }
    t0 = time.time()
    resp = json.load(post("/api/generate", body))
    wall = time.time() - t0
    return {
        "wall": wall,
        "total_ns": resp.get("total_duration", 0),
        "load_ns": resp.get("load_duration", 0),
        "prompt_count": resp.get("prompt_eval_count", 0),
        "prompt_ns": resp.get("prompt_eval_duration", 1) or 1,
        "eval_count": resp.get("eval_count", 0),
        "eval_ns": resp.get("eval_duration", 1) or 1,
    }


def ttft(model: str, prompt: str) -> float:
    body = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {"num_predict": NUM_PREDICT, "temperature": 0.0},
    }
    t0 = time.time()
    resp = post("/api/generate", body)
    for line in resp:
        if not line.strip():
            continue
        chunk = json.loads(line)
        if chunk.get("response"):
            return time.time() - t0
    return time.time() - t0


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def main() -> None:
    results = {}
    for model in MODELS:
        print(f"\n########## {model} ##########", flush=True)
        gen_once(model, "warmup")  # load model
        for size, prompt in SIZES.items():
            runs = [gen_once(model, prompt) for _ in range(REPEATS)]
            m = {k: median([r[k] for r in runs]) for k in runs[0]}
            prefill = m["prompt_count"] / (m["prompt_ns"] / 1e9)
            decode = m["eval_count"] / (m["eval_ns"] / 1e9)
            first = median([ttft(model, prompt) for _ in range(REPEATS)])
            results[(model, size)] = {
                "prompt_tokens": m["prompt_count"],
                "output_tokens": m["eval_count"],
                "prefill_tps": round(prefill, 1),
                "decode_tps": round(decode, 1),
                "ttft_s": round(first, 3),
                "total_s": round(m["total_ns"] / 1e9, 2),
                "load_s": round(m["load_ns"] / 1e9, 2),
            }
            r = results[(model, size)]
            print(f"  {size:14} prompt={r['prompt_tokens']:5} out={r['output_tokens']:4} "
                  f"prefill={r['prefill_tps']:7.1f} t/s  decode={r['decode_tps']:6.1f} t/s  "
                  f"ttft={r['ttft_s']:.2f}s  total={r['total_s']:.2f}s  load={r['load_s']:.2f}s",
                  flush=True)
    with open("/tmp/perf_results.json", "w", encoding="utf-8") as fh:
        json.dump({f"{k[0]}|{k[1]}": v for k, v in results.items()}, fh, ensure_ascii=False, indent=2)
    print("\nSaved /tmp/perf_results.json")


if __name__ == "__main__":
    main()
