#!/usr/bin/env python3
"""Local model benchmark — run 7 task tests on all available local models
and save detailed JSON reports to tests/test_reports/.

Usage:
    python tests/local_model_benchmark.py          # run all models
    python tests/local_model_benchmark.py --model qwen3:0.6b  # single model
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ---- Task definitions -------------------------------------------------------

TASKS: list[dict[str, Any]] = [
    {
        "id": "chat",
        "name": "Chinese Conversation",
        "system": "你是一个AI编程助手。用中文简洁回答。",
        "user": "你好，请用一句话介绍你自己。",
        "max_tokens": 400,
        "temperature": 0.1,
        "check": lambda c: len(c.strip()) > 5,
    },
    {
        "id": "code",
        "name": "Code Generation",
        "system": "输出纯Python代码，不要markdown，不要解释。",
        "user": "写一个函数 factorial(n) 返回n的阶乘",
        "max_tokens": 500,
        "temperature": 0.0,
        "check": lambda c: "def " in c and "return" in c,
    },
    {
        "id": "comprehension",
        "name": "Content Comprehension",
        "system": "根据给定的文件内容回答。只需输出答案。",
        "user": "文件内容如下:\n---\n项目: OpenLaoKe\n版本: 0.1.37\n许可证: GPL-3.0\n作者: OpenLaoKe Contributors\nPython版本要求: >=3.11\n---\n问: 许可证是什么？",
        "max_tokens": 200,
        "temperature": 0.0,
        "check": lambda c: "GPL" in c or "3.0" in c,
    },
    {
        "id": "tool_format",
        "name": "Tool Call Format",
        "system": (
            "你是一个coding agent。使用以下工具格式:\n"
            "<tool_call><function=NAME><parameter=key> value </tool_call>\n\n"
            "可用工具: Bash(command), Read(file_path), Write(file_path,content), "
            "Glob(pattern), Grep(pattern)"
        ),
        "user": "在 /tmp 目录下查找所有 .log 文件",
        "max_tokens": 400,
        "temperature": 0.1,
        "check": lambda c: (
            "tool_call" in c or "Bash" in c or "ls" in c.lower()
            or "Glob" in c or "find" in c.lower()
        ),
    },
    {
        "id": "read_file",
        "name": "Read File + Comprehension",
        "system": "你会收到文件内容。根据内容回答。",
        "user": (
            "文件 pyproject.toml 的内容:\n"
            "```\n"
            "[project]\n"
            'name = "openlaoke"\n'
            'requires-python = ">=3.11"\n'
            'license = "GPL-3.0-only"\n'
            'dependencies = ["anthropic>=0.40.0", "pydantic>=2.0", "rich>=13.0"]\n'
            "```\n\n"
            "这个项目的Python最低版本要求是什么？"
        ),
        "max_tokens": 300,
        "temperature": 0.0,
        "check": lambda c: "3.11" in c,
    },
    {
        "id": "multi_step",
        "name": "Multi-step Task Planning",
        "system": "你是一个coding agent。对多步骤任务，列出清晰的编号步骤和对应命令。",
        "user": (
            "任务:\n"
            "1. 创建 /tmp/olk_demo 目录\n"
            "2. 在里面创建 config.json 写入 {\"debug\": true}\n"
            "3. 验证文件已创建\n"
            "列出每个步骤要用的命令。"
        ),
        "max_tokens": 500,
        "temperature": 0.1,
        "check": lambda c: (
            ("mkdir" in c or "创建" in c)
            and ("config" in c.lower() or "json" in c.lower())
            and ("ls" in c.lower() or "cat" in c.lower() or "验证" in c)
        ),
    },
    {
        "id": "error_diag",
        "name": "Error Diagnosis",
        "system": "你是一个debugging专家。分析错误并给出修复方案。",
        "user": (
            "运行 python script.py 报错:\n"
            "```\n"
            "Traceback (most recent call last):\n"
            '  File "script.py", line 3, in <module>\n'
            "    result = data['key']\n"
            "KeyError: 'key'\n"
            "```\n"
            "原因是什么？怎么修？"
        ),
        "max_tokens": 500,
        "temperature": 0.1,
        "check": lambda c: (
            "KeyError" in c or "key" in c.lower() or "get(" in c
        ),
    },
]


# ---- Data types -------------------------------------------------------------


@dataclass
class TaskResult:
    task_id: str = ""
    task_name: str = ""
    passed: bool = False
    duration_s: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    system_prompt: str = ""
    user_prompt: str = ""
    response: str = ""


@dataclass
class ModelReport:
    model_name: str = ""
    provider: str = ""  # "ollama" or "gguf"
    model_size_mb: float = 0.0
    load_time_s: float = 0.0
    tasks: list[TaskResult] = field(default_factory=list)
    total_passed: int = 0
    total_tests: int = 0
    total_time_s: float = 0.0
    avg_time_s: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "provider": self.provider,
            "model_size_mb": self.model_size_mb,
            "load_time_s": self.load_time_s,
            "tasks": [asdict(t) for t in self.tasks],
            "total_passed": self.total_passed,
            "total_tests": self.total_tests,
            "total_time_s": self.total_time_s,
            "avg_time_s": self.avg_time_s,
            "timestamp": self.timestamp,
        }


# ---- Ollama test runner -----------------------------------------------------


async def test_ollama_model(
    model_name: str,
    base_url: str = "http://localhost:11434/v1",
    timeout: float = 180.0,
) -> ModelReport:
    import httpx

    print(f"\n{'='*70}")
    print(f"  TESTING: {model_name} (Ollama)")
    print(f"{'='*70}")

    report = ModelReport(
        model_name=model_name,
        provider="ollama",
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        for task_def in TASKS:
            task_id = task_def["id"]
            print(f"\n  [{task_id}] {task_def['name']} ... ", end="", flush=True)

            system = task_def["system"]
            user = task_def["user"]
            max_tok = task_def["max_tokens"]
            temp = task_def["temperature"]

            t0 = time.time()
            try:
                r = await client.post(f"{base_url}/chat/completions", json={
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": max_tok,
                    "temperature": temp,
                })
                r.raise_for_status()
            except Exception as e:
                print(f"API ERROR: {e}")
                report.tasks.append(TaskResult(
                    task_id=task_id, task_name=task_def["name"],
                    passed=False, duration_s=time.time()-t0,
                    system_prompt=system, user_prompt=user,
                    response=f"API ERROR: {e}",
                ))
                continue

            dt = time.time() - t0
            data = r.json()
            msg = data["choices"][0]["message"]
            content = (msg.get("content", "") or msg.get("reasoning", "")).strip()
            usage = data.get("usage", {})

            ok = task_def["check"](content)
            status = "PASS" if ok else "FAIL"
            print(f"{status} [{dt:.1f}s]")

            result = TaskResult(
                task_id=task_id,
                task_name=task_def["name"],
                passed=ok,
                duration_s=dt,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                system_prompt=system,
                user_prompt=user,
                response=content[:2000],
            )
            report.tasks.append(result)

    report.total_tests = len(report.tasks)
    report.total_passed = sum(1 for t in report.tasks if t.passed)
    report.total_time_s = sum(t.duration_s for t in report.tasks)
    report.avg_time_s = report.total_time_s / max(report.total_tests, 1)

    print(f"\n  RESULT: {report.total_passed}/{report.total_tests}  "
          f"Total: {report.total_time_s:.1f}s  Avg: {report.avg_time_s:.1f}s")

    return report


# ---- GGUF test runner -------------------------------------------------------


def test_gguf_model(
    model_path: str,
    n_ctx: int = 8192,
    n_threads: int = 8,
) -> ModelReport:
    from llama_cpp import Llama

    model_name = os.path.basename(model_path).replace(".gguf", "")
    print(f"\n{'='*70}")
    print(f"  TESTING: {model_name} (GGUF)")
    print(f"  Path: {model_path}")
    print(f"{'='*70}")

    size_mb = os.path.getsize(model_path) / (1024 * 1024)

    report = ModelReport(
        model_name=model_name,
        provider="gguf",
        model_size_mb=round(size_mb, 1),
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
    )

    t_load = time.time()
    llm = Llama(model_path=model_path, n_ctx=n_ctx, n_threads=n_threads, verbose=False)
    report.load_time_s = round(time.time() - t_load, 1)
    print(f"  Loaded in {report.load_time_s:.1f}s")

    for task_def in TASKS:
        task_id = task_def["id"]
        system = task_def["system"]
        user = task_def["user"]
        max_tok = task_def["max_tokens"]
        temp = task_def["temperature"]

        print(f"  [{task_id}] {task_def['name']} ... ", end="", flush=True)

        t0 = time.time()
        try:
            r = llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tok,
                temperature=temp,
            )
        except Exception as e:
            print(f"ERROR: {e}")
            report.tasks.append(TaskResult(
                task_id=task_id, task_name=task_def["name"],
                passed=False, duration_s=time.time()-t0,
                system_prompt=system, user_prompt=user,
                response=f"LLAMA ERROR: {e}",
            ))
            continue

        dt = time.time() - t0
        content = r["choices"][0]["message"]["content"].strip()
        usage = r.get("usage", {})

        ok = task_def["check"](content)
        status = "PASS" if ok else "FAIL"
        print(f"{status} [{dt:.1f}s]")

        result = TaskResult(
            task_id=task_id,
            task_name=task_def["name"],
            passed=ok,
            duration_s=dt,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            system_prompt=system,
            user_prompt=user,
            response=content[:2000],
        )
        report.tasks.append(result)

    del llm

    report.total_tests = len(report.tasks)
    report.total_passed = sum(1 for t in report.tasks if t.passed)
    report.total_time_s = sum(t.duration_s for t in report.tasks)
    report.avg_time_s = report.total_time_s / max(report.total_tests, 1)

    print(f"\n  RESULT: {report.total_passed}/{report.total_tests}  "
          f"Total: {report.total_time_s:.1f}s  Avg: {report.avg_time_s:.1f}s")

    return report


# ---- Main entry point -------------------------------------------------------


MODELS_TO_TEST: list[dict[str, str]] = [
    {"name": "qwen3:0.6b", "type": "ollama"},
    {"name": "huihui_ai/lfm2.5-abliterated:latest", "type": "ollama"},
    {
        "name": "Qwen3.5-2B-Q4_K_M",
        "type": "gguf",
        "path": os.path.expanduser("~/.openlaoke/models/Qwen3.5-2B-Q4_K_M.gguf"),
    },
]


def save_report(report: ModelReport, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    safe_name = report.model_name.replace("/", "_").replace(":", "_")
    ts = time.strftime("%Y%m%d-%H%M%S")
    filename = f"{safe_name}_{ts}.json"
    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False, default=str)
    print(f"  Report saved: {path}")
    return path


def print_summary(reports: list[ModelReport]) -> None:
    print("\n" + "=" * 80)
    print("  FINAL SUMMARY — ALL MODELS")
    print("=" * 80)
    print(f"  {'Model':40s} {'Score':8s} {'Time':8s} {'Avg':8s} {'Load':8s}")
    print(f"  {'-'*72}")
    for r in sorted(reports, key=lambda x: x.total_passed, reverse=True):
        medal = "🥇" if r.total_passed >= 7 else ("🥈" if r.total_passed >= 6 else "🥉")
        print(
            f"  {medal} {r.model_name[:38]:38s} "
            f"{r.total_passed}/{r.total_tests:<5} "
            f"{r.total_time_s:.1f}s{'':3s}"
            f"{r.avg_time_s:.1f}s{'':3s}"
            f"{r.load_time_s:.1f}s"
        )


def main() -> None:
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "test_reports"
    )

    # Filter by --model if specified
    target = None
    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        if idx + 1 < len(sys.argv):
            target = sys.argv[idx + 1]

    reports: list[ModelReport] = []

    for cfg in MODELS_TO_TEST:
        name = cfg["name"]
        if target and target not in name:
            continue

        if cfg["type"] == "ollama":
            report = asyncio.run(test_ollama_model(name))
        else:
            report = test_gguf_model(cfg["path"])

        reports.append(report)
        save_report(report, out_dir)

    print_summary(reports)

    # Also save collective summary
    summary_path = os.path.join(out_dir, f"_summary_{time.strftime('%Y%m%d-%H%M%S')}.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in reports], f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  Collective summary: {summary_path}")

    # Print failures for each model
    for r in reports:
        failed = [t for t in r.tasks if not t.passed]
        if failed:
            print(f"\n  {r.model_name} FAILURES:")
            for ft in failed:
                resp_preview = ft.response[:200].replace("\n", " ")
                print(f"    [{ft.task_id}] {ft.task_name}: {resp_preview}")


if __name__ == "__main__":
    main()
