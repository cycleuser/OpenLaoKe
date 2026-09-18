"""Compare OpenLaoKe and pi as harnesses across languages, using local models.

For each (harness, model, language) it sends a "introduce yourself" prompt in
that language and classifies the reply's language by script (Hangul → ko; kana
→ ja; CJK → zh; Cyrillic → ru) and, for Latin scripts, by stopword signatures.

pi must be configured with an OpenAI-compatible provider pointing at the local
server (see docs/benchmarks.md). Override the provider name with --pi-provider.

Usage:
    python scripts/bench_harness_multilang.py
    python scripts/bench_harness_multilang.py --models qwen3.5:2b --langs zh en ja
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_MODELS = [
    "qwen3.5:2b",
    "LiquidAI-dev/lfm2.5-2.6b:latest",
]

PROMPTS = {
    "zh": "请用一句话介绍你自己。",
    "en": "Introduce yourself in one sentence.",
    "ja": "一文で自己紹介してください。",
    "fr": "Présentez-vous en une phrase.",
    "ru": "Представьтесь одним предложением.",
    "de": "Stellen Sie sich in einem Satz vor.",
    "es": "Preséntate en una frase.",
    "pt": "Apresente-se em uma frase.",
    "it": "Presentati in una frase.",
    "ko": "한 문장으로 자기소개를 해 주세요.",
}

STOP = {
    "en": {"i", "am", "a", "an", "and", "the", "with", "for", "english", "assistant", "name", "my"},
    "fr": {"je", "suis", "un", "une", "et", "le", "la", "les", "pour", "avec", "français", "appelle", "mon"},
    "de": {"ich", "bin", "ein", "eine", "und", "der", "die", "das", "mit", "für", "deutsch", "heiße", "mein"},
    "es": {"soy", "un", "una", "y", "el", "la", "los", "con", "para", "español", "llamo", "mi", "asistente"},
    "pt": {"sou", "um", "uma", "e", "o", "a", "com", "para", "português", "chamo", "meu", "assistente"},
    "it": {"sono", "un", "una", "e", "il", "la", "con", "per", "italiano", "chiamo", "mio", "assistente"},
}


def detect(text: str) -> str:
    text = text.strip()
    if not text:
        return "empty"
    if re.search(r"[\uac00-\ud7a3]", text):
        return "ko"
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.search(r"[\u0400-\u04ff]", text):
        return "ru"
    words = set(re.findall(r"[a-zàâçéèêëîïôûùüÿñáíóúãõ]+", text.lower()))
    scores = {lang: len(words & stops) for lang, stops in STOP.items()}
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "?"


def run_one(
    harness: str, model: str, lang: str, base_url: str, pi_provider: str, max_tokens: int, timeout: int
) -> dict:
    prompt = PROMPTS[lang]
    if harness == "openlaoke":
        cmd = [
            sys.executable, "-m", "openlaoke",
            "--provider", "openai_compatible", "--base-url", base_url,
            "--api-key", "not-needed", "--model", model,
            "--max-tokens", str(max_tokens), "--cwd", "/tmp", prompt,
        ]
    else:
        cmd = [
            "pi", "-p", "--provider", pi_provider, "--model", model,
            "--no-skills", "--no-context-files", "--no-extensions",
            "--no-prompt-templates", "--no-themes", prompt,
        ]
    start = time.time()
    out = ""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        out = proc.stdout
    except subprocess.TimeoutExpired:
        out = ""
    if harness == "openlaoke":
        out = "\n".join(ln for ln in out.splitlines() if not ln.startswith("--- Session cost"))
    text = out.strip()
    return {
        "harness": harness,
        "model": model,
        "lang": lang,
        "detected": detect(text),
        "seconds": round(time.time() - start, 1),
        "text": text[:200],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    parser.add_argument("--pi-provider", default="ollama-local")
    parser.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    parser.add_argument("--langs", nargs="*", default=list(PROMPTS))
    parser.add_argument("--harnesses", nargs="*", default=["openlaoke", "pi"])
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--out", default="bench_harness_results.jsonl")
    args = parser.parse_args()

    if "pi" in args.harnesses and shutil.which("pi") is None:
        print("pi not found on PATH; skipping pi.")
        args.harnesses = [h for h in args.harnesses if h != "pi"]

    out_path = Path(args.out)
    results: dict[tuple[str, str], dict[str, str]] = {}
    for harness in args.harnesses:
        for model in args.models:
            for lang in args.langs:
                r = run_one(harness, model, lang, args.base_url, args.pi_provider, args.max_tokens, args.timeout)
                with out_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                results.setdefault((harness, model), {})[lang] = r["detected"]
                mark = "OK " if r["detected"] == lang else ".. "
                print(f"{harness:10} {model:32} {lang} {mark}{r['detected']:6} {r['seconds']:5.1f}s "
                      f"{r['text'][:36]!r}", flush=True)

    print("\n================ language match matrix ================")
    for harness in args.harnesses:
        print(f"\n--- {harness} ---")
        print("model".ljust(32) + "".join(lg.center(6) for lg in args.langs))
        for model in args.models:
            line = model.ljust(32)
            for lang in args.langs:
                d = results[(harness, model)][lang]
                line += ("OK" if d == lang else d).center(6)
            print(line)
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
