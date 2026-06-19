"""Anti-stall heuristic — detect think-phase responses and nudge the model to act.

Port of sekrun's ``shouldContinueForPromisedToolUse``.
When the model returns text-only output with no tool calls, this module checks
whether the content looks like a "plan / analysis / think phase" that intends
to proceed with tool calls. If so, the caller should inject a nudge instead
of ending the turn.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Chinese think-phase patterns
# ---------------------------------------------------------------------------

_CHINESE_PATTERNS: list[re.Pattern] = [
    re.compile(r"让我先.*(扫描|查看|检查|搜索|读取|阅读|分析|了解|理解|看一下|读一下)"),
    re.compile(r"我先.*(扫描|查看|检查|搜索|读取|阅读|分析|了解|理解|看一下|读一下)"),
    re.compile(r"先.*(扫描|查看|检查|搜索|读取|阅读|分析|了解|理解|看一下|读一下).*(项目|仓库|代码|文件|结构|实现|测试)"),
    re.compile(r"先.*(项目|仓库|代码|文件|结构|实现|测试).*(扫描|查看|检查|搜索|读取|阅读|分析|了解|理解|看一下|读一下)"),
    re.compile(r"接下来.*(我会|我准备|我将|开始|执行|动手|修改|实现|处理)"),
    re.compile(r"(计划|方案|思路|步骤).*(如下|是|：|:)"),
    re.compile(r"分析.*(完毕|完成).*接下来"),
    re.compile(r"理解.*(需求|问题|任务).*开始"),
    re.compile(r"总结.*(一下|如下).*接下来"),
    re.compile(r"让我(先)?.*(梳理|整理|理清)"),
    re.compile(r"以下.*我的.*(计划|方案|思路|分析)"),
    re.compile(r"我(计划|打算|准备|将|会).*分.*步"),
    re.compile(r"首先.*(读取|查看|搜索|检查|分析|理解).*然后"),
]

# ---------------------------------------------------------------------------
# English think-phase patterns
# ---------------------------------------------------------------------------

_ENGLISH_PATTERNS: list[re.Pattern] = [
    re.compile(r"let me (first )?(analyze|plan|think|understand|examine|review|study|outline)", re.IGNORECASE),
    re.compile(r"i'?ll (first )?(analyze|plan|think|understand|examine|review|study|outline)", re.IGNORECASE),
    re.compile(r"i(?:'ll| will) (first )?(inspect|scan|search|read|check|examine|review) ", re.IGNORECASE),
    re.compile(r"here('?s| is) my (plan|analysis|approach|strategy|outline)", re.IGNORECASE),
    re.compile(r"my (plan|analysis|approach) (is|will be|involves)", re.IGNORECASE),
    re.compile(r"let me start by (analyzing|examining|reviewing|checking|reading)", re.IGNORECASE),
    re.compile(r"first,.*(i'?ll|i will|let me).*(analyze|read|check|examine|review|understand|look)", re.IGNORECASE),
    re.compile(r"i will proceed (in|with|by)", re.IGNORECASE),
    re.compile(r"proposed (plan|approach|solution)", re.IGNORECASE),
    re.compile(r"step(-| )?1", re.IGNORECASE),
    re.compile(r"phase 1", re.IGNORECASE),
    re.compile(r"think.*execute", re.IGNORECASE),
    # Task-completion patterns that need more steps
    re.compile(r"task.*complete.*but.*(need|should|must|still)", re.IGNORECASE),
    re.compile(r"finished.*(main|primary).*(task|change).*(need|still|remaining)", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Fallback end-of-text patterns
# ---------------------------------------------------------------------------

_END_PATTERNS: list[re.Pattern] = [
    re.compile(r"proceed", re.IGNORECASE),
    re.compile(r"continue", re.IGNORECASE),
    re.compile(r"next", re.IGNORECASE),
    re.compile(r"开始"),
    re.compile(r"继续"),
    re.compile(r"下一步"),
    re.compile(r"执行"),
    re.compile(r"implement", re.IGNORECASE),
    re.compile(r"now .*(can|will|let)", re.IGNORECASE),
]

NUDGE_MESSAGE = (
    "Proceed now by using the appropriate tool calls, "
    "then provide the answer."
)


def should_continue_for_promised_tool_use(content: str) -> bool:
    """Check if text-only model output is a think-phase that needs a nudge.

    Returns ``True`` when the content appears to be a plan / analysis /
    thinking phase that intends to proceed with tool calls, so the caller
    should inject a nudge message instead of ending the turn.
    """
    text = (content or "").strip()
    if not text:
        return False

    lower = text.lower()

    if any(p.search(text) for p in _CHINESE_PATTERNS):
        return True

    if any(p.search(lower) for p in _ENGLISH_PATTERNS):
        return True

    # Fallback: if content has substantial text and ends with intent to proceed
    if len(text) > 200:
        end_lines = "\n".join(text.split("\n")[-3:]).lower()
        if any(p.search(end_lines) for p in _END_PATTERNS):
            return True

    return False
