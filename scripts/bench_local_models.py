"""Check local Ollama models through OpenLaoKe: plain, streaming, tool calling.

Usage:
    python scripts/bench_local_models.py
    python scripts/bench_local_models.py --base-url http://127.0.0.1:11434/v1 --models qwen3.5:2b granite4:350m-h
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

from openlaoke.core.multi_provider_api import MultiProviderClient
from openlaoke.types.providers import MultiProviderConfig, ProviderConfig, ProviderType

DEFAULT_MODELS = [
    "qwen3.5:2b",
    "qwen3.5:0.8b",
    "LiquidAI-dev/lfm2.5-2.6b:latest",
    "LiquidAI/lfm2.5-350m:latest",
    "lfm2.5-thinking:latest",
    "granite4:350m-h",
]


def _client(base_url: str, model: str) -> MultiProviderClient:
    provider = ProviderConfig(
        provider_type=ProviderType.OLLAMA, base_url=base_url, default_model=model, is_local=True
    )
    return MultiProviderClient(
        MultiProviderConfig(providers={"p": provider}, active_provider="p", active_model=model)
    )


async def plain(base_url: str, model: str, max_tokens: int) -> str:
    client = _client(base_url, model)
    try:
        msg, usage, _ = await client.send_message(
            "You are a test harness.",
            [{"role": "user", "content": "Reply with exactly the word: PONG"}],
            max_tokens=max_tokens,
            temperature=0.0,
        )
        text = (msg.content or "").strip().replace("\n", " ")
        return f"OK out={usage.output_tokens} {text[-40:]!r}" if "PONG" in text else f"?? {text[:40]!r}"
    except Exception as exc:  # noqa: BLE001
        return f"FAIL {type(exc).__name__}: {str(exc)[:60]}"
    finally:
        await client.close()


async def stream(base_url: str, model: str, max_tokens: int) -> str:
    client = _client(base_url, model)
    parts: list[str] = []
    try:
        async for chunk in client.stream_message(
            "You are a test harness.",
            [{"role": "user", "content": "Reply with exactly the word: PONG"}],
            max_tokens=max_tokens,
            temperature=0.0,
        ):
            if getattr(chunk, "text", None):
                parts.append(chunk.text)
        text = "".join(parts).strip()
        return f"OK {text[:40]!r}" if "PONG" in text else f"?? {text[:40]!r}"
    except Exception as exc:  # noqa: BLE001
        return f"FAIL {type(exc).__name__}: {str(exc)[:60]}"
    finally:
        await client.close()


def tools(base_url: str, model: str, max_tokens: int) -> str:
    with tempfile.TemporaryDirectory() as d:
        cmd = [
            sys.executable, "-m", "openlaoke",
            "--provider", "openai_compatible", "--base-url", base_url,
            "--api-key", "not-needed", "--model", model,
            "--max-tokens", str(max_tokens), "--yes", "--cwd", d,
            "Create a file named out.txt containing exactly: hello pi. Then run cat out.txt",
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=420, check=False)
        except subprocess.TimeoutExpired:
            return "TIMEOUT"
        target = Path(d) / "out.txt"
        if target.exists():
            return f"OK content={target.read_text().strip()!r}"
        return "FAIL (no file)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    parser.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    parser.add_argument("--max-tokens", type=int, default=2000)
    parser.add_argument("--skip-tools", action="store_true")
    args = parser.parse_args()

    print(f"{'model':32} {'plain':28} {'stream':24} tools")
    for model in args.models:
        p = asyncio.run(plain(args.base_url, model, args.max_tokens))
        s = asyncio.run(stream(args.base_url, model, args.max_tokens))
        t = "skipped" if args.skip_tools else tools(args.base_url, model, args.max_tokens)
        print(f"{model:32} {p:28} {s:24} {t}", flush=True)


if __name__ == "__main__":
    main()
