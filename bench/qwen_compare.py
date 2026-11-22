#!/usr/bin/env python
"""Run the LFM3 micro-benchmark against Qwen3.5-2B for comparison."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lfm3_compare import agent_test, quality_tests, speed_test  # noqa: E402

MODELS: list[dict[str, Any]] = [
    {
        "key": "qwen3.5-2b-mlx",
        "label": "Qwen3.5-2B MLX 4bit",
        "provider": "qwen3_5_2b_mlx",
        "base": "http://127.0.0.1:8084/v1",
        "model": "/Users/fred/models/qwen3.5-2b-mlx4",
        "runtime": "mlx_lm",
        "multimodal": False,
    },
    {
        "key": "qwen3.5-2b-gguf",
        "label": "Qwen3.5-2B GGUF Q4_K_M",
        "provider": "qwen3_5_2b_gguf",
        "base": "http://127.0.0.1:8085/v1",
        "model": "qwen3.5-2b",
        "runtime": "llama.cpp",
        "multimodal": False,
    },
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", action="store_true")
    parser.add_argument("--out", default="bench/results/qwen_compare.json")
    args = parser.parse_args()

    results: dict[str, Any] = {"created": time.time(), "models": {}}
    for model in MODELS:
        print(f"\n=== {model['label']} ===", flush=True)
        entry: dict[str, Any] = {
            "label": model["label"],
            "runtime": model["runtime"],
            "base": model["base"],
            "model": model["model"],
        }
        try:
            speed = speed_test(model)
            entry["speed"] = speed
            print(
                f"speed: {speed['median_generation_tps']} tok/s gen, "
                f"{speed['median_prompt_tps']} tok/s prompt, {speed['median_wall']}s",
                flush=True,
            )
            quality = quality_tests(model)
            entry["quality"] = quality
            print(
                f"quality: {sum(1 for item in quality if item['pass'])}/{len(quality)}", flush=True
            )
            for item in quality:
                print(
                    f"  {'PASS' if item['pass'] else 'FAIL'} {item['name']} "
                    f"({item['latency']}s) {item['detail'][:120]}",
                    flush=True,
                )
            if args.agent:
                agent = agent_test(model)
                entry["agent"] = agent
                print(
                    f"agent: {'PASS' if agent['pass'] else 'FAIL'} "
                    f"({agent['seconds']}s, exit={agent['exit_code']})",
                    flush=True,
                )
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
            print(f"ERROR: {entry['error']}", flush=True)
        results["models"][model["key"]] = entry

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out}", flush=True)


if __name__ == "__main__":
    main()
