# AGENTS.md - OpenLaoKe 开发指南

OpenLaoKe 是 [pi](https://github.com/earendil-works/pi) 的 Python 实现（Python 3.11+），
一个极简、快速、可扩展的终端编程智能体。设计上刻意贴近 pi：内核小，能力向外长。

## 开发命令

```bash
uv pip install -e ".[dev]"   # 安装（推荐）
pip install -e ".[dev]"

ruff check . && ruff format . # 检查+格式化
mypy                          # 类型检查（非严格）
pytest                        # 测试（asyncio_mode=auto）
```

单测试：`pytest tests/test_pi_commands.py -v`

## 运行模式

| 模式 | 命令 |
|------|------|
| TUI（默认） | `openlaoke` |
| 非交互 | `openlaoke "write a script"` |
| 本地模型管理 | `openlaoke model download/list/search/remove` |
| 配置向导 | `openlaoke --config` |

## 代码风格

- `from __future__ import annotations` + `TYPE_CHECKING` 守卫
- 导入顺序：标准库 → 第三方 → `openlaoke.` 绝对导入
- 类型注解：完整签名、`str | None`（不用 Optional）、dataclass、pydantic BaseModel
- 命名：类/PascalCase、函数/snake_case、常量/UPPER_SNAKE_CASE、私有/_前缀
- Ruff 规则：E, F, I, N, W, UP, B, SIM；行长 100
- 错误：返回 `ToolResultBlock(is_error=True)`，不抛异常

## 架构

```text
openlaoke/
├── entrypoints/cli.py     # argparse CLI + 配置向导入口
├── core/
│   ├── repl.py            # 交互循环、流式输出、工具分发
│   ├── agent_runner.py    # 与提供商无关的智能体回合
│   ├── multi_provider_api.py  # 多提供商客户端
│   ├── sessions.py        # 会话持久化（JSONL）
│   ├── snapshot/          # 按回合的文件 + 对话快照（fork/rewind）
│   ├── compact/           # fast_pruner 纯算法剪枝 + 摘要
│   ├── skill_system.py    # Agent Skills 加载器（SKILL.md）
│   ├── prompt_templates.py# pi 风格 prompt 模板
│   ├── cache_guard.py     # 字节稳定的系统提示词前缀
│   ├── hook_system.py     # 扩展点（tool_execute_before/after 等）
│   ├── system_prompt.py   # 系统提示词构建
│   └── tool.py            # Tool / ToolRegistry
├── tools/                 # read, write, edit, bash, grep, glob, ls, powershell, invoke_skill
├── commands/              # pi 命令集（base.py + pi_commands.py + skill_commands.py）
├── types/                 # 核心类型、providers、hooks、permissions
└── utils/                 # config、theme、diff、path_safety
```

## 关键实现

- **工具集**：`openlaoke/tools/register.py` 注册 pi 的 9 个工具。
- **命令**：`openlaoke/commands/pi_commands.py` 实现 pi 的内置命令；`registry.py` 统一注册。
- **prompt 模板**：`openlaoke/core/prompt_templates.py`，支持 `$1`/`$@`/`${1:-default}`/`${@:N:L}`。
- **技能**：`openlaoke/core/skill_system.py` + `tools/invoke_skill_tool.py`（渐进披露，正文按需加载）。
- **会话**：`openlaoke/core/sessions.py` + `openlaoke/snapshot/`。
- **压缩**：`openlaoke/core/compact/fast_pruner.py`（纯算法，<5ms，不调 LLM）。

## 配置路径

- 主配置：`~/.openlaoke/config.json`
- 会话：`~/.openlaoke/sessions/`
- 技能：`~/.openlaoke/skills/<name>/SKILL.md`（兼容 `~/.config/opencode/skills/`）
- prompt 模板：`~/.openlaoke/prompts/*.md`

## 重要约束

- **不要添加注释**，除非用户明确要求
- 工具 `call()` 方法用 `async def`
- 版本在 `openlaoke/__init__.py`（`__version__`）
- License：GPLv3（见 `LICENSE`）；pi 为 MIT，版权见 `THIRD_PARTY_NOTICES.md`
- 保持 pi 对齐：新增功能优先用技能 / prompt 模板 / 扩展点，而不是往内核堆工具
