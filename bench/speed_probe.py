#!/usr/bin/env python3
"""Raw model throughput probe: prefill + decode tokens/sec per OpenAI-compatible server.

Measures the model, not the agent. Same prompt, same max_tokens across every endpoint
so prefill and decode tokens/sec are directly comparable across GGUF (llama.cpp) and
MLX (mlx-vlm / mlx-lm) stacks.

No proxy. Local ports only. Never prints keys.

Usage:
  python bench/speed_probe.py --target lfm3-gguf=http://127.0.0.1:8080/v1:lfm3-1.7b \
      --target lfm3-mlx=http://127.0.0.1:8081/v1:/Users/fred/models/LFM3-1.7B-MLX-8bit \
      --repeats 3 --max-tokens 128
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request


def post_chat(base_url: str, model: str, prompt: str, max_tokens: int) -> dict:
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "stream": False,
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:  # local only; no proxy
        raw = resp.read().decode()
    elapsed = time.time() - t0
    obj = json.loads(raw)
    usage = obj.get("usage", {}) or {}
    # llama.cpp exposes timings; mlx-vlm may too. Use them when present.
    timings = obj.get("timings", {}) or {}
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    return {
        "elapsed": elapsed,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "timings": timings,
        "finish": (obj.get("choices") or [{}])[0].get("finish_reason", ""),
        "sample": ((obj.get("choices") or [{}])[0].get("message", {}) or {}).get(
            "content", ""
        )[:60],
    }


PROMPT = (
    "List the first 40 prime numbers, one per line, as fast as you can. "
    "No explanation."
)


def one_run(base_url: str, model: str, max_tokens: int) -> dict:
    r = post_chat(base_url, model, PROMPT, max_tokens)
    pt = r["prompt_tokens"]
    ct = r["completion_tokens"]
    timings = r["timings"]
    # llama.cpp timings: prompt_per_second, predicted_per_second
    prompt_tps = timings.get("prompt_per_second")
    decode_tps = timings.get("predicted_per_second")
    if prompt_tps is None and pt:
        prompt_tps = round(pt / r["elapsed"], 1) if r["elapsed"] else None
    if decode_tps is None and ct:
        decode_tps = round(ct / r["elapsed"], 1) if r["elapsed"] else None
    return {
        "elapsed": round(r["elapsed"], 2),
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "prompt_tps": round(prompt_tps, 1) if prompt_tps else None,
        "decode_tps": round(decode_tps, 1) if decode_tps else None,
        "finish": r["finish"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", action="append", required=True,
                    help="name=base_url:model (model may contain /)")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, default=128)
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy",
              "https_proxy", "all_proxy"):
        import os
        os.environ.pop(k, None)

    rows: list[dict] = []
    for spec in args.target:
        name, rest = spec.split("=", 1)
        base_url, model = rest.rsplit(":", 1)
        runs = [one_run(base_url, model, args.max_tokens) for _ in range(args.repeats)]
        median = lambda k: sorted(x[k] for x in runs)[len(runs) // 2]  # noqa: E731
        row = {
            "name": name,
            "base_url": base_url,
            "model": model,
            "repeats": runs,
            "median_elapsed": median("elapsed"),
            "median_prompt_tps": median("prompt_tps"),
            "median_decode_tps": median("decode_tps"),
            "prompt_tokens": runs[-1]["prompt_tokens"],
            "completion_tokens": runs[-1]["completion_tokens"],
        }
        rows.append(row)
        print(f"== {name} ({model})")
        for i, r in enumerate(runs):
            print(f"   run{i}: elapsed={r['elapsed']}s prompt_tps={r['prompt_tps']} "
                  f"decode_tps={r['decode_tps']} pt={r['prompt_tokens']} ct={r['completion_tokens']} "
                  f"finish={r['finish']}")
        print(f"   MEDIAN elapsed={row['median_elapsed']}s "
              f"prompt_tps={row['median_prompt_tps']} decode_tps={row['median_decode_tps']}")

    if args.json:
        with open(args.json, "w") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print("wrote", args.json)


if __name__ == "__main__":
    main()
