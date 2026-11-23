#!/usr/bin/env python3
"""A sixteen-question single-turn probe, wider than the first one.

Six families: arithmetic, reading code, writing code, instruction following,
data formats, and Chinese. No scoring happens here on purpose: the answers are
saved verbatim and graded by hand afterwards, because substring matching gets
these wrong in both directions (it once scored "100 minutes" as correct because
the string "5" appeared in "5 machines").

Usage:
  python bench/capability_probe2.py \
    --target spark=http://127.0.0.1:8093/v1:spark-1.7b-q4 \
    --target lfm3=http://127.0.0.1:8088/v1:lfm3-1.7b-q4 \
    --max-tokens 1024 --json bench/results/cap2.json
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request

QUESTIONS = [
    # --- arithmetic ---
    {
        "id": "pct_chain",
        "group": "算术",
        "q": "一件商品原价 40 元，先涨价 25%，再按新价降价 20%。最终价格多少元？只给数字。",
        "hint": "40 涨到 50，再降 20% 是 40",
    },
    {
        "id": "pct_back",
        "group": "算术",
        "q": "A number's 30% is 45. What is 10% of that number? Answer with just the number.",
        "hint": "150 的 10% = 15",
    },
    {
        "id": "sequence",
        "group": "算术",
        "q": "What number comes next: 2, 6, 12, 20, 30, ?  Answer with just the number.",
        "hint": "n(n+1)，下一个 42",
    },
    {
        "id": "rate",
        "group": "算术",
        "q": "A car covers 150 km in 2.5 hours. What is its average speed in km/h? "
        "Answer with just the number.",
        "hint": "60",
    },
    {
        "id": "zh_ratio",
        "group": "算术",
        "q": "一个班有 40 人，其中 60% 是女生，女生里有四分之一戴眼镜。戴眼镜的女生有多少人？"
        "只给数字。",
        "hint": "24 个女生中的 1/4 = 6",
    },
    # --- reading code ---
    {
        "id": "read_alias",
        "group": "读代码",
        "q": "What does this print?\n\n```python\nx = [1, 2, 3]\ny = x\ny.append(4)\nprint(len(x))\n```\n"
        "Answer with just the number.",
        "hint": "4，y 和 x 是同一个列表",
    },
    {
        "id": "read_slice",
        "group": "读代码",
        "q": "What does this print?\n\n```python\ns = \"abcdef\"\nprint(s[1:4][::-1])\n```\n"
        "Answer with just the string.",
        "hint": "bcd 反转 = dcb",
    },
    {
        "id": "read_scope",
        "group": "读代码",
        "q": "What does this print?\n\n```python\ndef f(a, b=[]):\n    b.append(a)\n    return b\n\n"
        "print(f(1), f(2))\n```\nAnswer with the exact output.",
        "hint": "[1, 2] [1, 2]，默认参数只求值一次",
    },
    {
        "id": "read_except",
        "group": "读代码",
        "q": "What does this print?\n\n```python\ntry:\n    print(int('7.5'))\n"
        "except ValueError:\n    print('value error')\n```\nAnswer with the exact output.",
        "hint": "value error",
    },
    # --- writing code ---
    {
        "id": "write_dedupe",
        "group": "写代码",
        "q": "Write one line of Python that turns the list `[3, 1, 3, 2, 1]` into `[3, 1, 2]`, "
        "keeping the first occurrence order. Code only.",
        "hint": "list(dict.fromkeys(...))",
    },
    {
        "id": "write_bugfix",
        "group": "写代码",
        "q": "This function should return the average of a list, but it crashes on an empty list "
        "and is wrong for odd cases: `def avg(xs): return sum(xs) / len(xs)`. "
        "Fix it in one line so an empty list returns 0.0. Code only.",
        "hint": "sum(xs)/len(xs) if xs else 0.0",
    },
    {
        "id": "write_regex",
        "group": "写代码",
        "q": "Write a Python regex that matches an ISO date like 2026-11-23 and captures year, "
        "month and day. Code only.",
        "hint": r"(\d{4})-(\d{2})-(\d{2})",
    },
    # --- instruction following ---
    {
        "id": "follow_format",
        "group": "指令",
        "q": "Reply with exactly three lines, each starting with '-' and containing exactly one "
        "colour word, in this order: red, green, blue. Nothing else.",
        "hint": "三行、只含颜色词",
    },
    {
        "id": "follow_negation",
        "group": "指令",
        "q": "Write one short sentence about the sea. Do not use the letter 'e' anywhere.",
        "hint": "不能出现字母 e",
    },
    # --- data formats ---
    {
        "id": "json_path",
        "group": "数据",
        "q": 'Given {"a": {"b": [1, 2, {"c": 3}]}}, what is the value at a.b[2].c? '
        "Answer with just the value.",
        "hint": "3",
    },
    {
        "id": "sql_null",
        "group": "数据",
        "q": "In SQL, what does `SELECT COUNT(*) FROM t WHERE x IS NULL` return? "
        "One short sentence.",
        "hint": "x 为 NULL 的行数",
    },
]

EXPECTED_GROUPS = ["算术", "读代码", "写代码", "指令", "数据"]


def ask(base_url: str, model: str, prompt: str, max_tokens: int) -> tuple[str, float]:
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
    started = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:
        payload = json.loads(resp.read().decode())
    elapsed = time.time() - started
    message = (payload.get("choices") or [{}])[0].get("message", {}) or {}
    return (message.get("content") or "").strip(), elapsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", action="append", required=True)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--json", default="")
    args = parser.parse_args()

    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(key, None)

    payload: list[dict] = []
    for spec in args.target:
        name, rest = spec.split("=", 1)
        base_url, model = rest.rsplit(":", 1)
        rows = []
        for item in QUESTIONS:
            answer, elapsed = ask(base_url, model, item["q"], args.max_tokens)
            rows.append({**item, "answer": answer, "seconds": round(elapsed, 1)})
            print(f"[{name}] {item['id']:15} {elapsed:5.1f}s -> {answer[:80]!r}", flush=True)
        payload.append({"name": name, "model": model, "rows": rows})

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=1)
        print("wrote", args.json)


if __name__ == "__main__":
    main()
