#!/usr/bin/env python3
"""Fixed text-capability probe for small local models via OpenAI-compatible server.

Same questions, same sampling across endpoints. Records raw answers; grading is by
eye against `expect`. No proxy. Local only. Never prints keys.

Usage:
  python bench/capability_probe.py --target name=base_url:model --json out.json
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request

QUESTIONS = [
    {
        "id": "math_arith",
        "q": "A shop sells 3 packs of 12 pens each for 45 dollars total. "
             "How many dollars is one pen? Answer with just the number.",
        "expect": "1.25",
    },
    {
        "id": "math_word",
        "q": "If 5 machines take 5 minutes to make 5 widgets, "
             "how many minutes do 100 machines take to make 100 widgets? One number.",
        "expect": "5",
    },
    {
        "id": "logic",
        "q": "All bloops are razzies. All razzies are lazzies. "
             "Are all bloops definitely lazzies? Answer yes or no.",
        "expect": "yes",
    },
    {
        "id": "code_reverse",
        "q": "Write one line of Python that prints the string 'hello' reversed.",
        "expect": "olleh",
    },
    {
        "id": "code_bug",
        "q": "This Python has one bug: def f(x): return x + 1; print(f('3')). "
             "What is the bug? One short sentence.",
        "expect": "str",
    },
    {
        "id": "follow_negation",
        "q": "Repeat this sentence but do NOT include the word 'cat': "
             "The cat sat on the mat.",
        "expect": "no cat",
    },
    {
        "id": "zh_translate",
        "q": "把这句英文翻译成中文：The server is temporarily unavailable.",
        "expect": "服务器",
    },
    {
        "id": "zh_math_word",
        "q": "一个水池有进水管和出水管，单开进水管6小时注满，单开出水管8小时放空。"
             "两管齐开，几小时注满？只给数字或分数。",
        "expect": "24",
    },
    {
        "id": "extract",
        "q": "From this log line extract the IP address only, nothing else: "
             "'2026-01-01 ERROR 192.168.1.42 connection refused'.",
        "expect": "192.168.1.42",
    },
    {
        "id": "count",
        "q": "How many words are in this sentence: 'to be or not to be that is the question'. "
             "Answer with just the number.",
        "expect": "10",
    },
]


def ask(base_url: str, model: str, prompt: str, max_tokens: int) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "stream": False,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as resp:
        obj = json.loads(resp.read().decode())
    dt = time.time() - t0
    msg = (obj.get("choices") or [{}])[0].get("message", {}) or {}
    return (msg.get("content") or "").strip(), dt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", action="append", required=True)
    ap.add_argument("--max-tokens", type=int, default=96)
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
              "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(k, None)

    all_rows = []
    for spec in args.target:
        name, rest = spec.split("=", 1)
        base_url, model = rest.rsplit(":", 1)
        rows = []
        for item in QUESTIONS:
            ans, dt = ask(base_url, model, item["q"], args.max_tokens)
            ok = item["expect"].lower() in ans.lower()
            rows.append({**item, "answer": ans[:4000], "auto_ok": ok, "seconds": round(dt, 1)})
            print(f"[{name}] {item['id']:18} ok={ok} ({dt:.1f}s) -> {ans[:70]!r}")
        auto = sum(r["auto_ok"] for r in rows)
        print(f"== {name} auto-match {auto}/{len(rows)}")
        all_rows.append({"name": name, "model": model, "auto": auto,
                         "total": len(rows), "rows": rows})
    if args.json:
        with open(args.json, "w") as f:
            json.dump(all_rows, f, ensure_ascii=False, indent=1)
        print("wrote", args.json)


if __name__ == "__main__":
    main()
