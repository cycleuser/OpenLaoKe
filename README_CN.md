# OpenLaoKe

开源终端AI编程助手。

## 特性

- **交互式REPL** - 丰富的终端UI界面
- **多提供商支持** - Anthropic、OpenAI、Ollama、LM Studio 以及自定义端点
- **工具系统** - 包含9个内置工具：
  - `Bash` - 执行shell命令，支持流式输出
  - `Read` - 读取文件内容，支持行范围
  - `Write` - 创建/覆盖文件
  - `Edit` - 精确的查找替换文件编辑，带diff输出
  - `Glob` - 快速文件模式匹配（遵循.gitignore）
  - `Grep` - 跨文件正则搜索，支持多种输出模式
  - `Agent` - 派生子代理并行工作
  - `Taskkill` - 终止运行中的任务
  - `NotebookWrite` - 写入Jupyter notebook单元格
- **MCP支持** - 连接外部MCP工具服务器
- **权限系统** - 三种模式：默认、自动、绕过
- **会话持久化** - 自动保存和恢复会话
- **成本追踪** - 实时显示token使用量和费用
- **斜杠命令** - 11个内置命令（`/help`、`/model`、`/cost`、`/compact`等）
- **钩子系统** - 可扩展的工具和API调用前后钩子
- **代理支持** - 无代理、系统代理或自定义代理

## 安装

```bash
# 克隆并安装
cd OpenLaoKe
pip install -e .

# 或使用uv（推荐）
uv pip install -e .
```

## 使用方法

```bash
# 首次运行（显示配置向导）
openlaoke

# 重新配置
openlaoke --config

# 非交互模式
openlaoke "Write a Python script that sorts a list"

# 带选项运行
openlaoke -m gpt-4o -p auto
openlaoke --provider ollama -m llama3.2
openlaoke --proxy http://127.0.0.1:7890
openlaoke --cwd /path/to/project
```

## 支持的提供商

| 提供商 | 类型 | 需要API密钥 |
|--------|------|-------------|
| Anthropic | 云端 | 是 |
| OpenAI | 云端 | 是 |
| Ollama | 本地 | 否 |
| LM Studio | 本地 | 否 |
| OpenAI兼容 | 自定义 | 可选 |

## 环境变量

| 变量 | 描述 |
|------|------|
| `ANTHROPIC_API_KEY` | Anthropic API密钥 |
| `OPENAI_API_KEY` | OpenAI API密钥 |
| `OPENLAOKE_MODEL` | 默认模型 |

## 斜杠命令

| 命令 | 描述 |
|------|------|
| `/help` | 显示可用命令 |
| `/exit` | 退出OpenLaoKe |
| `/clear` | 清除屏幕和对话 |
| `/model [name]` | 显示或切换模型 |
| `/permission [mode]` | 更改权限模式 |
| `/compact` | 压缩对话 |
| `/cost` | 显示会话费用和使用量 |
| `/cwd [path]` | 显示或切换工作目录 |
| `/resume` | 恢复上次会话 |
| `/commands` | 显示示例命令 |
| `/settings` | 显示当前设置 |

## 架构

```
openlaoke/
├── core/           # 核心系统
│   ├── state.py    # 集中式状态管理
│   ├── tool.py     # 工具基类和注册表
│   ├── task.py     # 任务生命周期管理
│   ├── multi_provider_api.py  # 多提供商API客户端
│   ├── repl.py     # REPL交互循环
│   ├── config_wizard.py  # 配置向导
│   └── ...
├── tools/          # 工具实现
├── commands/       # 斜杠命令
├── services/       # 外部服务（MCP）
├── components/     # UI组件（TUI）
├── types/          # 类型定义
└── utils/          # 工具函数
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行代码检查
ruff check .

# 运行测试
pytest

# 构建包
python -m build
```

## 配置

用户配置存储在 `~/.openlaoke/config.json`。你可以直接编辑它，或在REPL中使用 `/settings`。

## 许可证

GPLv3
