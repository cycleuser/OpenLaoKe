#!/usr/bin/env python
"""Compare LFM3 checkpoints served by llama.cpp and MLX-VLM.

Run with the four servers already listening on 8080-8083:
  python bench/lfm3_compare.py
  python bench/lfm3_compare.py --agent
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import re
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

MODELS: list[dict[str, Any]] = [
    {
        "key": "1.7b-gguf",
        "label": "LFM3-1.7B GGUF Q8_0",
        "provider": "lfm3_1_7b_gguf",
        "base": "http://127.0.0.1:8080/v1",
        "model": "lfm3-1.7b",
        "runtime": "llama.cpp",
        "multimodal": False,
    },
    {
        "key": "1.7b-mlx",
        "label": "LFM3-1.7B MLX 8bit",
        "provider": "lfm3_mlx",
        "base": "http://127.0.0.1:8081/v1",
        "model": "/Users/fred/models/LFM3-1.7B-MLX-8bit",
        "runtime": "MLX-VLM",
        "multimodal": False,
    },
    {
        "key": "omni-gguf",
        "label": "LFM3-Omni-2B GGUF Q8_0",
        "provider": "lfm3_omni_gguf",
        "base": "http://127.0.0.1:8083/v1",
        "model": "lfm3-omni-2b",
        "runtime": "llama.cpp",
        "multimodal": True,
    },
    {
        "key": "omni-mlx",
        "label": "LFM3-Omni-2B MLX 8bit",
        "provider": "lfm3_omni_mlx",
        "base": "http://127.0.0.1:8082/v1",
        "model": "/Users/fred/models/LFM3-Omni-2B-MLX-8bit",
        "runtime": "MLX-VLM",
        "multimodal": True,
    },
]

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write text to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    }
]

SPEED_PROMPT = (
    "Write a Python implementation of merge sort with docstrings and comments. "
    "Output only the code."
)


def chat(
    base: str,
    model: str,
    messages: list[dict[str, Any]],
    *,
    max_tokens: int = 256,
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.0,
    timeout: float = 300.0,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        body["tools"] = tools
    with httpx.Client(timeout=timeout, trust_env=False) as client:
        response = client.post(f"{base}/chat/completions", json=body)
        response.raise_for_status()
        return response.json()


def message_text(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content") or "")


def extract_code(text: str) -> str:
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.S)
    if match:
        return match.group(1).strip()
    stripped = text.strip()
    if stripped.startswith(("def ", "import ", "from ", "class ")):
        return stripped
    return stripped


def run_python(code: str, suffix: str = "") -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "check.py"
        path.write_text(code + "\n" + suffix, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(path)],
            cwd=tmp,
            capture_output=True,
            text=True,
            timeout=20,
        )
    output = (proc.stdout + proc.stderr).strip()
    return proc.returncode == 0, output


def extract_json(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None


def red_png_data_uri() -> str:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (255, 0, 0)).save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def quality_tests(model: dict[str, Any]) -> list[dict[str, Any]]:
    base, mid = model["base"], model["model"]
    results: list[dict[str, Any]] = []

    def record(name: str, passed: bool, latency: float, detail: str) -> None:
        results.append(
            {
                "name": name,
                "pass": passed,
                "latency": round(latency, 2),
                "detail": detail[:300],
            }
        )

    prompt = (
        "Write a Python function fib(n) that returns the nth Fibonacci number iteratively, "
        "and a __main__ block that prints fib(10). Output only the code, no explanation."
    )
    started = time.time()
    try:
        text = message_text(chat(base, mid, [{"role": "user", "content": prompt}], max_tokens=320))
        code = extract_code(text)
        ok, output = run_python(code)
        record("fib-code", ok and "55" in output, time.time() - started, output or text)
    except Exception as exc:
        record("fib-code", False, time.time() - started, f"{type(exc).__name__}: {exc}")

    prompt = (
        "Fix this Python function so add(a, b) returns the sum. "
        "Output only the corrected code:\n"
        "def add(a, b):\n    return a - b\n"
    )
    started = time.time()
    try:
        text = message_text(chat(base, mid, [{"role": "user", "content": prompt}], max_tokens=160))
        code = extract_code(text)
        ok, output = run_python(code, "\nprint(add(2, 3))")
        record("code-fix", ok and "5" in output, time.time() - started, output or text)
    except Exception as exc:
        record("code-fix", False, time.time() - started, f"{type(exc).__name__}: {exc}")

    prompt = (
        'Output only valid JSON with exactly these keys: "status" set to "ok", '
        '"count" set to 3, "items" set to ["a", "b", "c"]. No markdown.'
    )
    started = time.time()
    try:
        text = message_text(chat(base, mid, [{"role": "user", "content": prompt}], max_tokens=120))
        data = extract_json(text)
        passed = (
            isinstance(data, dict)
            and data.get("status") == "ok"
            and data.get("count") == 3
            and data.get("items") == ["a", "b", "c"]
        )
        record("json", passed, time.time() - started, text)
    except Exception as exc:
        record("json", False, time.time() - started, f"{type(exc).__name__}: {exc}")

    started = time.time()
    try:
        data = chat(
            base,
            mid,
            [
                {"role": "system", "content": "You are a coding agent. Use the provided tool."},
                {"role": "user", "content": "Create hello.txt with content hi using the tool."},
            ],
            max_tokens=180,
            tools=TOOLS,
        )
        message = (data.get("choices") or [{}])[0].get("message") or {}
        calls = message.get("tool_calls") or []
        call = calls[0] if calls else {}
        function = call.get("function") or {}
        try:
            arguments = json.loads(function.get("arguments") or "{}")
        except Exception:
            arguments = {}
        passed = (
            function.get("name") == "write_file"
            and arguments.get("path") == "hello.txt"
            and arguments.get("content") == "hi"
        )
        record("tool-call", passed, time.time() - started, json.dumps(calls, ensure_ascii=False))
    except Exception as exc:
        record("tool-call", False, time.time() - started, f"{type(exc).__name__}: {exc}")

    prompt = (
        "A shop sells pens for 2 yuan each and notebooks for 5 yuan each. "
        "I buy 4 pens and 3 notebooks. I pay with a 50 yuan note. "
        "How much change do I get? Answer with the number only."
    )
    started = time.time()
    try:
        text = message_text(chat(base, mid, [{"role": "user", "content": prompt}], max_tokens=400))
        record("reasoning", "27" in text, time.time() - started, text)
    except Exception as exc:
        record("reasoning", False, time.time() - started, f"{type(exc).__name__}: {exc}")

    started = time.time()
    try:
        text = message_text(
            chat(
                base,
                mid,
                [{"role": "user", "content": "Reply with exactly PONG and nothing else."}],
                max_tokens=32,
            )
        )
        record("instruction", text.strip().strip(".") == "PONG", time.time() - started, text)
    except Exception as exc:
        record("instruction", False, time.time() - started, f"{type(exc).__name__}: {exc}")

    if model["multimodal"]:
        started = time.time()
        try:
            data = chat(
                base,
                mid,
                [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "What color is this image? Answer one word."},
                            {
                                "type": "image_url",
                                "image_url": {"url": red_png_data_uri()},
                            },
                        ],
                    }
                ],
                max_tokens=32,
            )
            text = message_text(data)
            record("image-color", "red" in text.lower(), time.time() - started, text)
        except Exception as exc:
            record("image-color", False, time.time() - started, f"{type(exc).__name__}: {exc}")

    return results


def speed_test(model: dict[str, Any], runs: int = 3) -> dict[str, Any]:
    base, mid = model["base"], model["model"]
    for _ in range(2):
        chat(
            base,
            mid,
            [{"role": "user", "content": "Say OK"}],
            max_tokens=8,
            timeout=180,
        )

    samples: list[dict[str, float]] = []
    for _ in range(runs):
        started = time.time()
        data = chat(
            base,
            mid,
            [{"role": "user", "content": SPEED_PROMPT}],
            max_tokens=220,
            timeout=300,
        )
        wall = time.time() - started
        timings = data.get("timings") or {}
        usage = data.get("usage") or {}
        generated = float(usage.get("completion_tokens") or timings.get("predicted_n") or 0)
        predicted_tps = timings.get("predicted_per_second")
        if predicted_tps is None and wall > 0:
            predicted_tps = generated / wall
        samples.append(
            {
                "wall": wall,
                "generated": generated,
                "generation_tps": float(predicted_tps or 0),
                "prompt_tps": float(timings.get("prompt_per_second") or 0),
            }
        )

    return {
        "runs": samples,
        "median_wall": round(statistics.median(s["wall"] for s in samples), 2),
        "median_generation_tps": round(statistics.median(s["generation_tps"] for s in samples), 2),
        "median_prompt_tps": round(statistics.median(s["prompt_tps"] for s in samples), 2),
        "median_generated": round(statistics.median(s["generated"] for s in samples), 1),
    }


def agent_test(model: dict[str, Any], timeout: float = 150.0) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="lfm3_agent_") as tmp:
        prompt = "Create hello.py that prints 42. Run it to verify."
        command = [
            sys.executable,
            "-m",
            "openlaoke",
            "--provider",
            model["provider"],
            "--model",
            model["model"],
            "--local",
            "-c",
            tmp,
            prompt,
        ]
        started = time.time()
        timed_out = False
        try:
            proc = subprocess.run(
                command,
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            exit_code = proc.returncode
            log = (proc.stdout + proc.stderr)[-4000:]
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = None
            log = str(exc.stdout or "")[-4000:]
        elapsed = time.time() - started
        target = Path(tmp) / "hello.py"
        output_ok = False
        output = ""
        if target.exists():
            check = subprocess.run(
                [sys.executable, str(target)],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=20,
            )
            output = (check.stdout + check.stderr).strip()
            output_ok = "42" in output
        return {
            "pass": bool(target.exists() and output_ok and not timed_out),
            "timeout": timed_out,
            "exit_code": exit_code,
            "seconds": round(elapsed, 2),
            "file_created": target.exists(),
            "output": output,
            "log_tail": log[-1200:],
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", action="store_true", help="also run one OpenLaoKe task")
    parser.add_argument("--out", default="", help="write JSON results here")
    args = parser.parse_args()

    results: dict[str, Any] = {"created": time.time(), "models": {}}
    for model in MODELS:
        print(f"\n=== {model['label']} ===", flush=True)
        entry: dict[str, Any] = {
            "label": model["label"],
            "runtime": model["runtime"],
            "multimodal": model["multimodal"],
            "base": model["base"],
            "model": model["model"],
        }
        try:
            speed = speed_test(model)
            entry["speed"] = speed
            print(
                f"speed: {speed['median_generation_tps']} tok/s gen, "
                f"{speed['median_wall']}s wall, {speed['median_generated']} tokens",
                flush=True,
            )
            quality = quality_tests(model)
            entry["quality"] = quality
            passed = sum(1 for item in quality if item["pass"])
            print(f"quality: {passed}/{len(quality)}", flush=True)
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

    out = (
        Path(args.out)
        if args.out
        else Path("bench/results") / f"lfm3_compare_{int(time.time())}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out}", flush=True)


if __name__ == "__main__":
    main()
