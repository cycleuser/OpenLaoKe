# AGENTS.md - OpenLaoKe 开发指南

OpenLaoKe 是一个开源的终端AI编程助手（Python 3.11+ CLI），类似于 Claude Code 或 Cursor。

## 项目概述

### 目标
- 与 Claude Code 和 OpenCode 实现全面功能对等
- HyperAuto 模式 - 完全自主运行，自我改进
- 反AI检测 - 确保生成内容不被检测为AI生成
- 任务监督 - 自动重试和完成验证
- 模型能力评估 - 根据模型能力调整任务粒度

### 参考项目
参考 `/Users/fred/Documents/GitHub/Others/` 目录下的项目：
- `opencode` - OpenCode CLI工具
- `Openclaude` - OpenClaude项目
- `deer-flow` - Deer Flow项目

## 开发命令

### 安装
```bash
uv pip install -e ".[dev]"   # 安装开发依赖（推荐）
pip install -e ".[dev]"      # 使用pip安装
```

### 代码检查与格式化
```bash
ruff check .                 # 代码检查
ruff check . --fix           # 自动修复
ruff format .                # 格式化代码
```

### 类型检查
```bash
mypy                         # 运行mypy（非严格模式）
mypy openlaoke/core/         # 检查特定目录
```

### 测试
```bash
pytest                       # 完整测试套件
pytest --cov                 # 带覆盖率
pytest tests/test_tools.py   # 单个文件
pytest tests/test_tools.py::TestBashTool::test_simple_command  # 单个测试
pytest -v                    # 详细输出
pytest -x                    # 首次失败时停止
pytest -k "keyword"          # 按名称过滤
```

## 代码风格

### 导入
- 每个模块顶部使用 `from __future__ import annotations`
- 导入顺序：标准库 → 第三方 → 本地（由 ruff `I` 规则强制）
- 使用 `TYPE_CHECKING` 守卫避免循环导入
- 使用 `openlaoke.` 前缀的绝对导入（不用相对导入）

### 类型注解
- 所有函数签名必须有完整类型注解（参数 + 返回值）
- 使用 `|` 表示联合类型（如 `str | None`，不用 `Optional[str]`）
- 数据结构使用 `dataclass`
- 工具输入模式使用 `pydantic BaseModel`
- 常量使用 `Enum`（如 `PermissionMode`、`TaskStatus`）

### 命名约定
- 类名：`PascalCase`（如 `AppState`、`ToolRegistry`）
- 函数/方法：`snake_case`（如 `create_app_state`、`check_tool`）
- 常量：`UPPER_SNAKE_CASE`（如 `PREFIXES`、`MAX_TOKENS`）
- 私有属性：前导下划线（如 `_listeners`、`_persist_path`）

### 格式化
- 行长度：100字符（E501被忽略，软限制）
- Ruff规则：E, F, I, N, W, UP, B, SIM
- mypy：非严格模式，但会警告 `return Any` 和未使用的忽略

### 错误处理
- 工具方法返回 `ToolResultBlock` 并设置 `is_error=True`，而不是抛出异常
- 非关键操作使用 `try/except Exception` 并静默通过
- 验证返回 `ValidationResult(result=False, message=..., error_code=...)`
- 记录错误，不要崩溃 REPL

### 异步模式
- 工具的 `call()` 方法使用 `async def`
- 测试使用 "auto" 模式的 `pytest-asyncio`
- 全程使用 `asyncio` 进行异步操作

### 文档字符串
- 每个文件都有模块级文档字符串
- 关键类有类级文档字符串
- 抽象/重要方法有方法文档字符串

**重要：不要添加任何注释，除非用户明确要求。**

## 架构

```
openlaoke/
├── core/                      # 核心系统
│   ├── state.py              # 集中式状态管理（dataclass，观察者模式，持久化）
│   ├── tool.py               # 工具基类和注册表
│   ├── task.py               # 任务生命周期管理
│   ├── multi_provider_api.py # 多提供商API客户端
│   ├── repl.py               # REPL交互循环
│   ├── config_wizard.py      # 配置向导
│   ├── system_prompt.py      # 系统提示生成
│   ├── agent_runner.py       # 子代理运行器
│   ├── supervisor/           # 任务监督系统
│   │   ├── supervisor.py     # 主监督器（任务解析，重试逻辑）
│   │   ├── checker.py        # 需求检查器（反AI，参考文献）
│   │   └── requirements.py   # 任务需求定义
│   ├── model_assessment/     # 模型能力评估
│   │   ├── assessor.py       # ModelAssessor, TaskDecomposer类
│   │   └── types.py          # ModelTier, TaskGranularity, CapabilityScore
│   ├── hyperauto/            # HyperAuto模式
│   │   ├── agent.py          # 主代理
│   │   ├── skill_generator.py # 自动技能生成
│   │   ├── project_initializer.py # 项目初始化
│   │   ├── code_search.py    # 代码搜索引擎
│   │   └── workflow.py       # 工作流编排
│   ├── skill_system.py       # 技能管理
│   ├── memory/               # 持久化内存
│   ├── scheduler/            # 任务调度
│   └── compact/              # 对话压缩
├── tools/                    # 工具实现（30+）
│   ├── bash_tool.py          # Bash工具
│   ├── read_tool.py          # Read工具
│   ├── write_tool.py         # Write工具
│   ├── edit_tool.py          # Edit工具
│   ├── glob_tool.py          # Glob工具
│   ├── grep_tool.py          # Grep工具
│   ├── agent_tool.py         # Agent工具
│   ├── batch_tool.py         # Batch工具
│   ├── web_search.py         # WebSearch工具
│   ├── web_fetch.py          # WebFetch工具
│   ├── lsp_tool.py           # LSP工具
│   ├── git_tool.py           # Git工具
│   ├── todo_tool.py          # TodoWrite工具
│   ├── reference_downloader.py # 参考文献下载工具
│   └── ...                   # 其他工具
├── commands/                 # 斜杠命令（20+）
│   ├── base.py               # 命令基类和实现
│   ├── registry.py           # 命令注册表
│   ├── hyperauto_command.py  # HyperAuto命令
│   └── skill_commands.py     # 技能命令
├── types/                    # 类型定义
│   ├── core_types.py         # 核心类型
│   ├── permissions.py        # 权限类型
│   ├── providers.py          # 提供商类型
│   └── hooks.py              # 钩子类型
├── services/                 # 外部服务
│   └── mcp/                  # MCP服务
├── components/               # UI组件
│   └── ...                   # Rich-based TUI组件
├── utils/                    # 工具函数
│   ├── config.py             # 配置管理
│   └── compute.py            # 计算工具
├── hooks/                    # 钩子实现
└── entrypoints/              # CLI入口点
    └── cli.py                # 主CLI
```

## 核心模式

### 状态管理
- **AppState**：集中式状态（dataclass，观察者模式，持久化）
- **Session persistence**：自动保存和恢复会话
- **Observer pattern**：状态变更通知

### 工具系统
- **Tool基类**：抽象基类，定义 `call()` 方法
- **ToolResultBlock**：统一的结果类型
- **Tool Registry**：动态工具注册

### 命令系统
- **SlashCommand基类**：抽象基类
- **Command Registry**：命令注册表
- **Alias支持**：命令别名

### 提供商系统
- **MultiProviderClient**：多提供商API客户端
- **Provider适配器**：针对不同提供商的适配器
- **模型发现**：自动检测可用模型

### 技能系统
- **YAML-based**：基于YAML的技能定义
- **Dynamic loading**：动态加载技能
- **Skill shortcuts**：技能快捷方式

## 关键实现细节

### 模型评估系统

**文件位置**：`openlaoke/core/model_assessment/`

**主要类**：
- `ModelTier`：模型层级枚举（5个层级）
- `TaskGranularity`：任务粒度配置
- `ModelAssessor`：模型能力评估器
- `TaskDecomposer`：任务分解器

**使用示例**：
```python
from openlaoke.core.model_assessment import ModelAssessor, TaskDecomposer

# 评估模型
assessor = ModelAssessor(config)
benchmark = await assessor.assess_model(api, "gemma3:1b", "ollama")

# 获取任务粒度
granularity = assessor.get_granularity("gemma3:1b")

# 分解任务
decomposer = TaskDecomposer(granularity)
steps = decomposer.decompose("Write an article and create a diagram")
```

### 任务监督系统

**文件位置**：`openlaoke/core/supervisor/`

**主要类**：
- `TaskSupervisor`：主监督器
- `SupervisedTask`：被监督的任务
- `TaskCompletionChecker`：完成检查器
- `TaskRequirements`：任务需求定义

**使用示例**：
```python
from openlaoke.core.supervisor import TaskSupervisor

supervisor = TaskSupervisor(app_state)
supervisor.set_model("gemma3:1b", config)

# 解析请求
task = supervisor.parse_request("Write an article about machine learning")

# 检查完成
result = await supervisor.check_completion(task_id, artifacts)

# 获取重试提示
if result.should_retry:
    prompt = supervisor.get_retry_prompt(task_id, result)
```

### HyperAuto模式

**文件位置**：`openlaoke/core/hyperauto/`

**主要功能**：
- 自动任务分解和执行
- 自我验证和改进
- 技能生成
- 项目初始化

**触发方式**：
```bash
/hyperauto on
/hyperauto --mode autonomous
```

### 反AI检测

**集成位置**：
- `openlaoke/core/supervisor/checker.py` - 检查逻辑
- `~/.config/opencode/skills/academic-writer/SKILL.md` - 写作指南
- 系统提示词

**检测模式**：
- 没有实质内容的编号列表
- 模糊声明
- 通用短语
- 缺乏具体引用
- 缺少技术深度

**强制要求**：
- 真实可下载的引用
- 具体数字和度量
- 代码引用带行号
- 完整段落
- 技术深度

## 配置与数据存储

### 配置路径
- 主配置：`~/.openlaoke/config.json`
- 会话文件：`~/.openlaoke/sessions/`
- 模型基准：`~/.openlaoke/model_benchmarks/`
- 技能目录：`~/.config/opencode/skills/`

### 工作目录数据
- 参考文献PDF：`pdf/` 目录
- 项目分析：`.openlaoke/` 目录

## 已知问题与解决方案

### Batch工具bug
**问题**：`'dict' object has no attribute 'tool_name'`

**解决方案**：在 `batch_tool.py` 中添加dict到ToolCallSpec的转换

### Agent工具代理错误
**问题**：`Unknown scheme for proxy URL URL('')`

**解决方案**：在 `agent_tool.py` 中检查空代理字符串

### 会话文件污染
**问题**：文件创建在项目根目录

**解决方案**：移动到 `~/.openlaoke/sessions/`

### 技能调用
**问题**：`/skill-name args` 格式不工作

**解决方案**：修复REPL在技能激活后继续处理

### 工具名称不匹配
**问题**：工具名称不一致

**解决方案**：
- `LS` → `ListDirectory`
- `Todo` → `TodoWrite`
- `NotebookEdit` → `NotebookWrite`

## 开发工作流

### 添加新工具
1. 在 `openlaoke/tools/` 创建新文件
2. 继承 `Tool` 基类
3. 实现 `call()` 方法
4. 在 `openlaoke/tools/__init__.py` 注册
5. 在 `openlaoke/core/tool.py` 的工具注册表中注册

### 添加新命令
1. 在 `openlaoke/commands/base.py` 创建新类
2. 继承 `SlashCommand`
3. 实现 `execute()` 方法
4. 在 `openlaoke/commands/registry.py` 注册

### 添加新提供商
1. 在 `openlaoke/types/providers.py` 添加提供商类型
2. 在 `MultiProviderConfig.defaults()` 添加默认配置
3. 在 `openlaoke/core/multi_provider_api.py` 添加API适配器
4. 在 `openlaoke/core/config_wizard.py` 添加配置向导支持

### 添加新技能
1. 创建技能目录：`~/.config/opencode/skills/<skill-name>/`
2. 创建 `SKILL.md` 文件
3. 定义技能指令和工作流
4. 使用 `/skill <name>` 调用

## 性能优化

### Token使用
- 使用对话压缩减少上下文大小
- 智能消息截断
- 保留关键消息

### 并行执行
- 使用Batch工具并行执行多个工具
- Agent工具并行派发子任务

### 模型选择
- 根据任务复杂度选择合适层级的模型
- 简单任务使用小模型节省成本
- 复杂任务使用大模型确保质量

## 测试策略

### 单元测试
- 每个工具的独立测试
- 命令测试
- 核心功能测试

### 集成测试
- REPL流程测试
- 多提供商集成测试
- 端到端工作流测试

### 覆盖率
- 目标覆盖率：80%+
- 关键模块：90%+

## 发布流程

### 版本管理
- 版本号存储在 `openlaoke/__init__.py`
- 遵循语义版本控制

### 发布步骤
1. 更新版本号
2. 更新CHANGELOG
3. 运行所有测试
4. 构建包：`python -m build`
5. 发布到PyPI：`twine upload dist/*`

## 贡献指南

### 代码贡献
1. Fork项目
2. 创建特性分支
3. 编写代码和测试
4. 确保所有测试通过
5. 提交Pull Request

### 文档贡献
1. 更新README.md和README_CN.md
2. 更新AGENTS.md
3. 添加代码文档字符串

### 问题报告
1. 描述问题和复现步骤
2. 提供系统信息
3. 附上错误日志

## 联系方式

- GitHub Issues: https://github.com/cycleuser/OpenLaoKe/issues
- 项目地址: https://github.com/cycleuser/OpenLaoKe