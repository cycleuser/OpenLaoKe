import json
import re
import subprocess
from pathlib import Path

ROOT = Path.home() / "Downloads" / "openlaoke-pi-small-models"
rows = [json.loads(ln) for ln in (ROOT / "results.jsonl").read_text().splitlines() if ln.strip()]


def run_py(work: Path, name: str) -> str:
    f = work / name
    if not f.exists():
        return ""
    try:
        p = subprocess.run(["python3", str(f)], cwd=work, capture_output=True, text=True, timeout=60)
        return (p.stdout + p.stderr).strip()
    except Exception as e:  # noqa: BLE001
        return f"ERR {e}"


def evaluate(r) -> tuple[bool, str]:
    work = Path(r["workdir"])
    t = r["task"]
    out = r["stdout"]
    if t == "T1_write_exact":
        f = work / "hello.txt"
        ok = f.exists() and "hello small model" in f.read_text(errors="ignore")
        return ok, "file" if f.exists() else "no file"
    if t == "T2_read_sum":
        ok = bool(re.search(r"\b224\b", out))
        return ok, "224" if ok else "no 224"
    if t == "T3_fib_run":
        f = work / "fib.py"
        if not f.exists():
            return False, "no fib.py"
        o = run_py(work, "fib.py")
        nums = re.findall(r"\d+", o)
        seq = ["0", "1", "1", "2", "3", "5", "8", "13", "21", "34"]
        ok = any(nums[i:i+10] == seq for i in range(len(nums)))
        return ok, "seq ok" if ok else f"out={o[:40]!r}"
    if t == "T4_report_md":
        f = work / "report.md"
        if not f.exists():
            return False, "no report.md"
        raw = f.read_text(errors="ignore")
        txt = raw.replace("\\n", "\n")
        bullets = len(re.findall(r"^\s*([-*]|\d+\.)\s+", txt, re.M))
        literal = "\\n" in raw
        return (("#" in txt) and bullets >= 3), f"bullets={bullets} literal_n={literal}"
    if t == "T5_fix_bug":
        f = work / "buggy.py"
        if not f.exists():
            return False, "no buggy.py"
        fixed = "+ 1" not in f.read_text(errors="ignore")
        o = run_py(work, "buggy.py")
        ok = fixed and re.search(r"\b4(\.0)?\b", o)
        return bool(ok), ("fixed" if fixed else "unfixed") + f" out={o[:20]!r}"
    return False, "?"


models = ["qwen3.5:2b", "LiquidAI-dev/lfm2.5-2.6b:latest"]
tasks = ["T1_write_exact", "T2_read_sum", "T3_fib_run", "T4_report_md", "T5_fix_bug"]
langs = ["zh", "en"]
harnesses = ["openlaoke", "pi"]

for r in rows:
    r["ok"], r["note"] = evaluate(r)


def cell(h, m, lg, t):
    for r in rows:
        if r["harness"] == h and r["model"] == m and r["lang"] == lg and r["task"] == t:
            return r
    return None


print("== 任务正确率 (OK) ==  rows: harness/model/lang, cols: tasks ==")
for h in harnesses:
    for m in models:
        for lg in langs:
            line = f"{h:9} {m:32} {lg} "
            for t in tasks:
                r = cell(h, m, lg, t)
                line += ("OK " if r and r["ok"] else ".. ").ljust(5)
            print(line)

print("\n== 按 任务 汇总 (OK / 8) ==")
for t in tasks:
    ok = sum(1 for r in rows if r["task"] == t and r["ok"])
    print(f"  {t:16} {ok}/{len(harnesses)*len(models)*len(langs)}")

print("\n== 按 模型 汇总 (OK / 20) ==")
for m in models:
    ok = sum(1 for r in rows if r["model"] == m and r["ok"])
    print(f"  {m:32} {ok}/{len(harnesses)*len(langs)*len(tasks)}")

print("\n== 按 外壳 汇总 (OK / 20) ==")
for h in harnesses:
    ok = sum(1 for r in rows if r["harness"] == h and r["ok"])
    print(f"  {h:10} {ok}/{len(models)*len(langs)*len(tasks)}")

print("\n== 按 语言 汇总 ==")
for lg in langs:
    ok = sum(1 for r in rows if r["lang"] == lg and r["ok"])
    print(f"  {lg}: {ok}/{len(harnesses)*len(models)*len(tasks)}")

print("\n== 失败的格子明细 ==")
for r in rows:
    if not r["ok"]:
        print(f"  {r['harness']:9} {r['model'][:22]:22} {r['lang']} {r['task']:16} {r['seconds']:6.1f}s  {r['note']}")
