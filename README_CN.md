# OpenLaoKe

> 开源终端AI编程助手，支持本地模型、高级自动化和智能监督。

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: GPLv3](https://img.shields.io/badge/license-GPLv3-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

## 简介

OpenLaoKe 是一款功能强大的终端AI编程助手，支持 **24+ AI提供商**、**本地GGUF模型**（零API费用）和**高级自动化**功能。无论你需要云端智能还是完全离线的AI编程，OpenLaoKe 都能满足。

## 核心特性

### 基础功能
- **交互式REPL** — 丰富的终端UI，命令历史（↑/↓、Ctrl+R），智能补全（Tab）
- **多提供商支持** — 24个AI提供商，涵盖云端、本地和免费选项
- **本地GGUF模型** — 零API费用、零网络需求运行Qwen模型
- **Ctrl+P模型选择器** — VS Code风格的模型切换弹窗，即时切换提供商/模型
- **30+内置工具** — Read、Write、Edit、Glob、Grep、Bash、LSP、Git、WebSearch等
- **MCP支持** — 连接外部MCP工具服务器
- **权限系统** — 三种模式：默认、自动、绕过
- **会话持久化** — 自动保存和恢复对话
- **成本追踪** — 实时显示token使用量和费用
- **20+斜杠命令** — 模型切换、配置、调试等
- **钩子系统** — 可扩展的前后执行钩子
- **代理支持** — 无代理、系统代理或自定义代理

### 高级功能
- **HyperAuto模式** — 完全自主运行，自我改进和技能生成
- **任务监督** — 自动重试、完成验证和质量检查
- **模型评估** — 5层自适应任务分解，基于模型能力
- **反AI检测** — 确保生成内容像人类撰写，带真实引用
- **蒸馏提示词模板** — 79个预置Q&A模板，覆盖31个类别，支持8种语言触发（中/英/日/韩/法/德/西/俄）
- **参考文献下载** — 学术写作自动下载PDF
- **技能系统** — 39+基于YAML的专业工作流技能
- **小模型优化** — 工具参数类型强制、JSON Schema清理、读循环预防、终端输出压缩、模型尺寸自适应行为，专为GGUF模型（0.6B-8B）优化
- **快速上下文修剪** — 纯算法上下文压缩（<5ms，无需LLM），头尾保护+关键词提取
- **钩子系统** — 15个扩展点，支持工具执行前后、消息转换、错误处理等
- **自我反思追踪器** — 基于实证数据的策略追踪，自动禁用失败方法并推荐更优方案

## 快速开始

```bash
# 使用pip安装
pip install -e .

# 或使用uv（推荐）
uv pip install -e ".[dev]"

# 安装本地GGUF模型支持（llama-cpp-python）
pip install -e ".[local]"

# 启动OpenLaoKe
openlaoke
```

## 支持的提供商

### 免费模型（无需API密钥）
| 提供商 | 模型 | 说明 |
|--------|------|------|
| **OpenCode Zen** | `big-pickle`, `gpt-5-nano` | 完全免费，无需注册 |
| **内置GGUF** | `qwen3:0.6b`, `qwen2.5:0.5b/1.5b/3b` | 本地CPU推理，零费用 |

### 云端提供商
| 提供商 | 模型 | API密钥 |
|--------|------|---------|
| Anthropic | Claude 4 Sonnet/Opus, Claude 3.5 | 是 |
| OpenAI | GPT-4o, GPT-4o-mini, o1-preview | 是 |
| MiniMax | MiniMax-M2.7, M2.5, M2.1 | 是 |
| 阿里云编程计划 | Qwen3.5-plus, Kimi-k2.5, GLM-5 | 是 |
| Azure OpenAI | GPT-4o, GPT-4o-mini, GPT-35-turbo | 是 |
| Google AI | Gemini 2.0 Flash/Pro, 1.5 Flash/Pro | 是 |
| Google Vertex AI | 通过GCP访问Gemini | 是 |
| AWS Bedrock | Claude 3.5, Llama 3.1, Amazon Nova | 是 |
| xAI Grok | Grok-2-latest, Grok-beta | 是 |
| Mistral AI | Mistral-large, Mistral-small, Codestral | 是 |
| Groq | Llama 3.3 70B, Llama 3.1 8B | 是 |
| Cerebras | Llama 3.3 70B, Llama 3.1 8B/70B | 是 |
| Cohere | Command-r-plus, Command-r | 是 |
| DeepInfra | Llama 3.3/3.1, Mistral-small | 是 |
| Together AI | Llama 3.3/3.1, Mistral, Qwen 2.5 | 是 |
| Perplexity | Sonar系列模型 | 是 |
| OpenRouter | 多提供商访问 | 是 |
| GitHub Copilot | GPT-4o, GPT-4o-mini, o1 | 是 |

### 本地提供商
| 提供商 | 模型 | 设置 |
|--------|------|------|
| Ollama | Gemma 3/4, Llama 3.1/3.2, CodeLlama | 安装Ollama |
| LM Studio | 任意本地模型 | 安装LM Studio |
| **内置GGUF** | Qwen模型, 任意ModelScope GGUF | `pip install -e ".[local]"` |
| OpenAI兼容 | 任意OpenAI兼容端点 | 自定义URL |

## 本地GGUF模型（零API费用）

完全在本地运行AI模型，无需API密钥或网络连接。基于 [llama-cpp-python](https://github.com/abetlen/llama-cpp-python)。

### 安装
```bash
pip install -e ".[local]"
```

### 内置模型
| 模型 | 大小 | 最小内存 | 描述 |
|------|------|----------|------|
| Qwen3 0.6B | 610 MB | 1 GB | 阿里Qwen3，中英文支持优秀 |
| Qwen2.5 0.5B | 469 MB | 512 MB | 超小模型，资源占用最低 |
| Qwen2.5 1.5B | 1 GB | 2 GB | 速度与质量的良好平衡 |
| Qwen2.5 3B | 1.9 GB | 4 GB | 更好的推理和编码能力 |

### 下载模型
```bash
# 下载内置模型
openlaoke model download qwen3:0.6b

# 搜索ModelScope上的任意GGUF模型
openlaoke model search qwen3.5

# 下载自定义模型
openlaoke model download "unsloth/Qwen3.5-0.8B-GGUF"

# 列出所有模型及状态
openlaoke model list

# 删除已下载的模型
openlaoke model remove custom:unsloth-Qwen3.5-0.8B-GGUF
```

### 配置方法
1. 运行 `openlaoke --config`，选择选项 **3**（Built-in GGUF Model）
2. 从列表中选择模型（内置或自定义下载）
3. 如需下载，可直接在向导中完成

### 本地模型参数
通过REPL中的 `/localconfig` 或 `~/.openlaoke/config.json` 配置：

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `n_ctx` | 262144 | 上下文窗口大小（模型最大值） |
| `temperature` | 0.3 | 采样温度（越低越确定） |
| `repetition_penalty` | 1.1 | 重复惩罚（减少复读） |

```bash
# 在REPL中调整
/localconfig n_ctx 32768
/localconfig temperature 0.5
/localconfig repetition_penalty 1.2
```

### 本地模型特性
- **自定义模型注册持久化** — 模型信息跨重启保存，存储在 `~/.openlaoke/models/custom_models.json`
- **蒸馏提示词模板** — 79个Q&A模板自动作为few-shot上下文注入，提升小模型表现
- **量化版本自动替换** — 从同一仓库下载新版本时自动替换旧量化
- **精简版系统提示词** — 小模型约30 token vs 完整版约800 token
- **`
</think>

` 思考内容显示** — Qwen3.5的思考过程解析并显示
- **上下文感知截断** — 自动截断消息以适应上下文窗口
- **Ctrl+P模型选择器** — REPL中即时切换模型

## 工具系统（30+工具）

### 文件操作
| 工具 | 描述 |
|------|------|
| **Read** | 读取文件内容，支持行范围 |
| **Write** | 创建/覆盖文件 |
| **Edit** | 精确查找替换，带diff输出 |
| **Glob** | 快速文件模式匹配（遵循.gitignore） |
| **Grep** | 跨文件正则搜索 |
| **LS** | 列出目录内容 |

### 代码智能
| 工具 | 描述 |
|------|------|
| **LSP** | 语言服务器协议集成 |
| **Git** | Git操作（status, diff, log, blame） |
| **Bash** | 执行shell命令，支持流式输出 |

### 网络与搜索
| 工具 | 描述 |
|------|------|
| **WebSearch** | 搜索网络信息 |
| **WebFetch** | 获取网页内容 |
| **SearchAndDownloadPapers** | 搜索学术论文 |

### 任务管理
| 工具 | 描述 |
|------|------|
| **TodoWrite** | 管理任务列表 |
| **Taskkill** | 终止运行中的任务 |
| **Batch** | 并行执行多个工具 |
| **Agent** | 派生子代理并行工作 |

### 其他工具
Notebook支持（Read/Write）、Cron计划任务、Memory存储、Hook配置、参考文献管理（Download/Batch/Manager）。

## 斜杠命令

### 模型与提供商管理
| 命令 | 描述 |
|------|------|
| `/model` | 显示当前模型和可用模型 |
| `/model <name>` | 切换到指定模型 |
| `/model <1-N>` | 通过序号选择模型 |
| `/model <provider>/<model>` | 切换提供商和模型 |
| `/model -l` | 列出所有提供商的所有模型 |
| `/model -p` | 列出所有提供商 |
| `/provider` | 显示当前提供商 |
| `/provider <name>` | 切换到不同提供商 |
| `/localconfig` | 配置本地模型参数 |
| **Ctrl+P** | **模型选择器弹窗** |

### 本地模型管理（CLI）
| 命令 | 描述 |
|------|------|
| `openlaoke model download [id]` | 下载内置或ModelScope GGUF模型 |
| `openlaoke model list` | 列出所有模型及状态 |
| `openlaoke model search <关键词>` | 搜索ModelScope上的GGUF模型 |
| `openlaoke model remove <id>` | 删除已下载的模型 |
| `openlaoke model info <id>` | 查看模型详情 |

### 会话与配置
| 命令 | 描述 |
|------|------|
| `/help` | 显示可用命令 |
| `/exit` | 退出OpenLaoKe |
| `/clear` | 清除屏幕和对话 |
| `/resume` | 恢复上次会话 |
| `/compact` | 压缩对话以节省上下文 |
| `/permission [mode]` | 更改权限模式 |
| `/settings` | 显示当前设置 |
| `/theme [name]` | 更改颜色主题 |
| `/cwd [path]` | 显示或切换工作目录 |

### 信息与高级
| 命令 | 描述 |
|------|------|
| `/cost` | 显示会话费用和使用量 |
| `/usage` | 显示详细使用统计 |
| `/commands` | 显示示例命令 |
| `/doctor` | 诊断配置问题 |
| `/hooks` | 管理钩子 |
| `/mcp` | 管理MCP服务器 |
| `/hyperauto` | 启动HyperAuto的模式 |
| `/skill <name>` | 执行技能 |
| `/memory` | 管理持久化内存 |
| `/agents` | 管理子代理 |
| `/lessons` | 查看跨项目经验教训和策略统计 |

## 蒸馏提示词模板

79个预置Q&A模板，覆盖31个类别，支持 **8种语言触发**（中/英/日/韩/法/德/西/俄）。匹配用户输入时自动作为few-shot上下文注入。

### 类别覆盖
| 类别 | 模板数 | 覆盖内容 |
|------|--------|----------|
| **系统命令** | 9 | 系统信息、进程、网络、磁盘、用户、服务、日志、安全、包管理 |
| **Shell脚本** | 10 | 基础、条件、循环、函数、文本处理、错误处理、I/O、数组、字符串、数学 |
| **工具调用** | 5 | 何时使用Bash、Read、Write、Edit、Glob/Grep |
| **算法** | 10 | 排序、查找、树、图、动态规划、链表、栈、哈希、递归、贪心 |
| **文件操作** | 6 | 读取、写入、CSV、路径、JSON、YAML |
| **数据库** | 4 | SQL、SQLite、ORM、Redis |
| **网络** | 3 | HTTP请求、网页爬取、WebSocket |
| **Python高级** | 3 | 装饰器、异步编程、上下文管理器 |
| **其他** | 29 | Git、测试、调试、OOP、DevOps、CLI、Web、数学、代码审查、机器学习等 |

### 工作原理
```
用户输入: "用Python写一个快速排序"
→ 匹配 "code_sort" 模板（触发词: "排序"）
→ 将快速排序示例注入系统提示词
→ 小模型参考示例生成更好的代码
```

## 技能系统（39+技能）

基于YAML的专业工作流技能：

| 技能 | 描述 |
|------|------|
| `/academic-writer` | 学术论文写作（AAAI, IJCAI, IEEE） |
| `/browse` | 用于QA测试的无头浏览器 |
| `/qa` | 系统性QA测试和bug修复 |
| `/debug` | 根本原因调查的系统性调试 |
| `/design-review` | 视觉QA和设计打磨 |
| `/ship` | 发布工作流（合并、测试、创建PR） |
| `/retro` | 每周工程回顾 |
| `/office-hours` | YC风格创业咨询 |
| `/brief-write` | 简洁写作风格 |
| `/humanizer` | 人性化AI生成的文本 |
| `/power-iterate` | 持续自主迭代 |
| `/skill-refiner` | 改进和完善技能 |

## 架构

```
openlaoke/
├── core/                      # 核心系统
│   ├── state.py              # 集中式状态管理
│   ├── tool.py               # 工具基类和注册表
│   ├── multi_provider_api.py # 多提供商API客户端
│   ├── repl.py               # REPL交互循环
│   ├── config_wizard.py      # 配置向导
│   ├── prompt_input.py       # 带Ctrl+P选择器的提示输入
│   ├── system_prompt.py      # 系统提示词构建器（本地模型精简版）
│   ├── local_model_manager.py # 本地GGUF模型注册表和下载
│   ├── builtin_model_provider.py # llama-cpp-python推理提供者
│   ├── model_cli.py          # CLI模型管理命令
│   ├── distilled_templates.py # 蒸馏提示词模板
│   ├── small_model_optimizations.py # 小模型优化（类型强制、schema清理、输出压缩）
│   ├── hook_system.py        # 15钩子扩展系统
│   ├── bitter_lesson_tracker.py # 自我反思与策略追踪
│   ├── cross_project_lessons.py # 跨项目经验教训数据库
│   ├── compact/              # 上下文压缩系统
│   │   ├── fast_pruner.py    # 纯算法上下文修剪（<5ms）
│   │   ├── strategies.py     # 压缩策略
│   │   └── summarizer.py     # 基于LLM的摘要
│   ├── supervisor/           # 任务监督系统
│   ├── model_assessment/     # 模型能力评估
│   ├── hyperauto/            # HyperAuto模式
│   ├── skill_system.py       # 技能管理
│   └── memory/               # 持久化内存
├── tools/                    # 工具实现（30+）
├── commands/                 # 斜杠命令（20+）
├── types/                    # 类型定义
├── services/mcp/             # MCP服务
├── server/                   # Web API和UI
├── utils/                    # 工具函数
├── hooks/                    # 钩子实现
└── entrypoints/cli.py        # CLI入口点
```

## 运行模式

### 在线模式（默认）
```bash
openlaoke
```
直接调用云端API。适合GPT-4o、Claude 4等强大模型。

### 本地模式
```bash
openlaoke --local
```
原子任务分解 + 监督。适合小型本地模型。

### Web UI
```bash
openlaoke web --host 0.0.0.0 --port 8080
```
完整Web界面，支持局域网访问。

### API Server
```bash
openlaoke server
```
FastAPI后端，localhost:3000。

## 命令行选项

```bash
# 非交互模式
openlaoke "写一个排序列表的Python脚本"

# 指定模型和提供商
openlaoke -m gpt-4o --provider openai
openlaoke --provider ollama -m llama3.2

# 使用代理
openlaoke --proxy http://127.0.0.1:7890

# 设置工作目录
openlaoke --cwd /path/to/project

# 恢复上次会话
openlaoke --resume

# 重新配置
openlaoke --config

# 本地模式，用于小型模型
openlaoke --local --provider ollama -m gemma3:1b
```

## 配置

配置存储在 `~/.openlaoke/config.json`：

```json
{
  "providers": {
    "active_provider": "local_builtin",
    "active_model": "custom:unsloth-Qwen3.5-0.8B-GGUF",
    "local_n_ctx": 262144,
    "local_temperature": 0.3,
    "local_repetition_penalty": 1.1,
    "providers": {
      "local_builtin": {
        "default_model": "custom:unsloth-Qwen3.5-0.8B-GGUF",
        "enabled": true
      },
      "ollama": {
        "base_url": "http://localhost:11434/v1",
        "default_model": "gemma3:1b",
        "enabled": true
      }
    }
  },
  "proxy_mode": "none",
  "max_tokens": 8192,
  "temperature": 1.0,
  "theme": "dark"
}
```

自定义模型注册信息存储在 `~/.openlaoke/models/custom_models.json`，重启后自动加载。会话文件存储在 `~/.openlaoke/sessions/`。

## 环境变量

| 变量 | 描述 |
|------|------|
| `ANTHROPIC_API_KEY` | Anthropic API密钥 |
| `OPENAI_API_KEY` | OpenAI API密钥 |
| `MINIMAX_API_KEY` | MiniMax API密钥 |
| `ALIYUN_API_KEY` | 阿里云编程计划API密钥 |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API密钥 |
| `GOOGLE_API_KEY` | Google AI API密钥 |
| `XAI_API_KEY` | xAI API密钥 |
| `MISTRAL_API_KEY` | Mistral API密钥 |
| `GROQ_API_KEY` | Groq API密钥 |
| `CEREBRAS_API_KEY` | Cerebras API密钥 |
| `COHERE_API_KEY` | Cohere API密钥 |
| `DEEPINFRA_API_KEY` | DeepInfra API密钥 |
| `TOGETHERAI_API_KEY` | Together AI API密钥 |
| `PERPLEXITY_API_KEY` | Perplexity API密钥 |
| `OPENROUTER_API_KEY` | OpenRouter API密钥 |
| `GITHUB_TOKEN` | GitHub个人访问令牌 |
| `OPENLAOKE_MODEL` | 默认模型 |
| `HTTP_PROXY` / `HTTPS_PROXY` | 代理设置 |

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 代码检查和格式化
ruff check . && ruff format .

# 类型检查
mypy

# 运行测试
pytest
pytest --cov
pytest tests/test_tools.py::TestBashTool::test_simple_command

# 构建包
python -m build
```

## 贡献

欢迎贡献！请：

1. Fork本仓库
2. 创建特性分支（`git checkout -b feature/amazing-feature`）
3. 提交更改（`git commit -m 'Add amazing feature'`）
4. 推送到分支（`git push origin feature/amazing-feature`）
5. 创建Pull Request

## 许可证

GPLv3
