"""Verify OpenLaoKe's OpenAI and Anthropic (Claude) provider formats.

OpenAI format is exercised against a real OpenAI-compatible endpoint (set
DEEPSEEK_API_KEY or pass --openai-base-url/--openai-api-key). The Anthropic
format is exercised against a local mock server that asserts the exact request
contract, so no Anthropic key is required.

Usage:
    python scripts/bench_provider_formats.py
    python scripts/bench_provider_formats.py --local-base-url http://127.0.0.1:11434/v1 --local-model llama3.2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from openlaoke.core.multi_provider_api import MultiProviderClient
from openlaoke.types.providers import MultiProviderConfig, ProviderConfig, ProviderType

RECEIVED: dict[str, object] = {}


def _config(provider: ProviderConfig, model: str) -> MultiProviderConfig:
    return MultiProviderConfig(providers={"p": provider}, active_provider="p", active_model=model)


class _AnthropicMock(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        RECEIVED.update({"path": self.path, "headers": dict(self.headers), "body": body})
        payload = {
            "id": "msg_mock_1",
            "type": "message",
            "role": "assistant",
            "model": body.get("model", "claude"),
            "content": [{"type": "text", "text": "PONG"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 11, "output_tokens": 2},
        }
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


async def check_openai(base_url: str, api_key: str, model: str) -> None:
    if not api_key:
        print("[OpenAI format] SKIP (no key)")
        return
    provider = ProviderConfig(
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        api_key=api_key,
        base_url=base_url,
        default_model=model,
    )
    client = MultiProviderClient(_config(provider, model))
    try:
        msg, usage, _ = await client.send_message(
            "You are a test harness.",
            [{"role": "user", "content": "Reply with exactly the word: PONG"}],
            max_tokens=32,
            temperature=0.0,
        )
        print(f"[OpenAI format] OK  text={msg.content!r}  out={usage.output_tokens}")
    except Exception as exc:  # noqa: BLE001
        print(f"[OpenAI format] FAIL {type(exc).__name__}: {str(exc)[:120]}")
    finally:
        await client.close()


async def check_anthropic_mock() -> None:
    server = HTTPServer(("127.0.0.1", 0), _AnthropicMock)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    provider = ProviderConfig(
        provider_type=ProviderType.ANTHROPIC,
        api_key="sk-ant-test",
        base_url=f"http://127.0.0.1:{port}",
        default_model="claude-3-5-haiku-20241022",
    )
    client = MultiProviderClient(_config(provider, "claude-3-5-haiku-20241022"))
    try:
        msg, usage, _ = await client.send_message(
            "You are a test harness.",
            [{"role": "user", "content": "Reply with exactly: PONG"}],
            max_tokens=32,
            temperature=0.0,
        )
        body = RECEIVED.get("body", {})
        headers = RECEIVED.get("headers", {})
        ok = (
            RECEIVED.get("path") == "/v1/messages"
            and headers.get("anthropic-version") == "2023-06-01"
            and msg.content == "PONG"
            and body.get("system") == "You are a test harness."
        )
        print(f"[Anthropic format] {'PASS' if ok else 'FAIL'}  path={RECEIVED.get('path')} "
              f"text={msg.content!r} in={usage.input_tokens} out={usage.output_tokens}")
    except Exception as exc:  # noqa: BLE001
        print(f"[Anthropic format] FAIL {type(exc).__name__}: {str(exc)[:120]}")
    finally:
        await client.close()
        server.shutdown()


async def check_local(base_url: str, model: str) -> None:
    provider = ProviderConfig(
        provider_type=ProviderType.OLLAMA, base_url=base_url, default_model=model, is_local=True
    )
    client = MultiProviderClient(_config(provider, model))
    try:
        msg, usage, _ = await client.send_message(
            "You are a test harness.",
            [{"role": "user", "content": "Reply with exactly the word: PONG"}],
            max_tokens=200,
            temperature=0.0,
        )
        print(f"[Local OpenAI-compatible] OK  text={msg.content!r}  out={usage.output_tokens}")
    except Exception as exc:  # noqa: BLE001
        print(f"[Local OpenAI-compatible] FAIL {type(exc).__name__}: {str(exc)[:120]}")
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openai-base-url", default="https://api.deepseek.com/v1")
    parser.add_argument("--openai-api-key", default=os.environ.get("DEEPSEEK_API_KEY", ""))
    parser.add_argument("--openai-model", default="deepseek-chat")
    parser.add_argument("--local-base-url", default="http://127.0.0.1:11434/v1")
    parser.add_argument("--local-model", default="qwen3.5:2b")
    parser.add_argument("--skip-local", action="store_true")
    args = parser.parse_args()

    asyncio.run(check_openai(args.openai_base_url, args.openai_api_key, args.openai_model))
    asyncio.run(check_anthropic_mock())
    if not args.skip_local:
        asyncio.run(check_local(args.local_base_url, args.local_model))


if __name__ == "__main__":
    main()
