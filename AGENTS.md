# AGENTS.md - OpenLaoKe 开发指南

OpenLaoKe 是开源终端AI编程助手（Python 3.11+），类 Claude Code。

## 开发命令

```bash
uv pip install -e ".[dev]"   # 安装（推荐）
pip install -e ".[dev]"

ruff check . && ruff format . # 检查+格式化
mypy                          # 类型检查（非严格）
pytest                        # 测试（asyncio_mode=auto）
```

单测试：`pytest tests/test_tools.py::TestBashTool::test_simple_command -v`

## 运行模式

| 模式 | 命令 | 特点 |
|------|------|------|
| TUI（默认） | `openlaoke` | 交互式终端界面 |
| Web UI | `openlaoke web` | 完整Web界面，支持局域网访问 |
| API Server | `openlaoke server` | FastAPI后端（localhost:3000） |
| 本地模式 | `openlaoke --local` | 原子分解+监督，适合小模型 |

Web UI：`openlaoke web --host 0.0.0.0 --port 8080`（默认局域网可访问）

## 代码风格

- `from __future__ import annotations` + `TYPE_CHECKING` 守卫
- 导入顺序：标准库 → 第三方 → `openlaoke.` 绝对导入
- 类型注解：完整签名、`str | None`（不用Optional）、dataclass、pydantic BaseModel
- 命名：类/PascalCase、函数/snake_case、常量/UPPER_SNAKE_CASE、私有/_前缀
- Ruff规则：E, F, I, N, W, UP, B, SIM；行长100（E501忽略）
- 错误：返回 `ToolResultBlock(is_error=True)`，不抛异常

## 架构

```
openlaoke/
├── core/                    # 核心：state, tool, repl, multi_provider_api
│   ├── supervisor/         # 任务监督（反AI检测、参考文献）
│   ├── model_assessment/   # 模型评估（5层tier系统）
│   └── hyperauto/          # HyperAuto自主模式
├── tools/                  # 30+工具（bash/read/write/edit/glob/grep/agent/batch等）
├── commands/                # 20+斜杠命令（base.py+registry.py）
├── types/                  # 类型定义
├── services/mcp/           # MCP服务
├── server/                 # Web服务（server.py=API, web_ui.py=Web UI）
└── entrypoints/cli.py      # CLI入口
```

## 关键实现

**模型评估**：`openlaoke/core/model_assessment/` - `ModelAssessor`、`TaskDecomposer`
**任务监督**：`openlaoke/core/supervisor/` - `TaskSupervisor`、`TaskCompletionChecker`
**反AI检测**：`openlaoke/core/supervisor/checker.py` - 强制引用、数字、技术深度

## 配置路径

- 主配置：`~/.openlaoke/config.json`
- 会话：`~/.openlaoke/sessions/`
- 技能：`~/.config/opencode/skills/`

## 重要约束

- **不要添加注释**，除非用户明确要求
- 工具`call()`方法用`async def`
- 版本在`openlaoke/__init__.py`（`__version__`）
- License: GPLv3（README/ LICENSE），非pyproject.toml中的MIT
