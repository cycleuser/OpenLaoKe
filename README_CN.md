# OpenLaoKe

开源终端AI编程助手，具备高级自动化和监督能力。

## 特性

### 核心功能
- **交互式REPL** - 丰富的终端UI界面
- **多提供商支持** - 支持22个AI提供商
- **工具系统** - 30+内置工具
- **MCP支持** - 连接外部MCP工具服务器
- **权限系统** - 三种模式：默认、自动、绕过
- **会话持久化** - 自动保存和恢复会话
- **成本追踪** - 实时显示token使用量和费用
- **斜杠命令** - 20+内置命令
- **钩子系统** - 可扩展的前后钩子
- **代理支持** - 无代理、系统代理或自定义代理

### 高级功能
- **HyperAuto模式** - 完全自主运行，自我改进
- **任务监督** - 自动重试和完成验证
- **模型评估** - 基于模型能力的自适应任务分解
- **反AI检测** - 确保生成内容看起来像人类撰写
- **参考文献下载** - 学术写作自动下载PDF
- **技能系统** - 基于YAML的技能系统，动态加载

## 支持的提供商（22个）

| 提供商 | 类型 | 需要API密钥 | 模型示例 |
|--------|------|-------------|----------|
| Anthropic | 云端 | 是 | Claude 4 Sonnet, Claude 4 Opus, Claude 3.5 Sonnet/Haiku |
| OpenAI | 云端 | 是 | GPT-4o, GPT-4o-mini, GPT-4-turbo, o1-preview, o1-mini |
| MiniMax | 云端 | 是 | MiniMax-M2.7, MiniMax-M2.5, MiniMax-M2.1 |
| 阿里云编程计划 | 云端 | 是 | Qwen3.5-plus, Kimi-k2.5, GLM-5, Qwen3-max |
| Azure OpenAI | 云端 | 是 | GPT-4o, GPT-4o-mini, GPT-4-turbo, GPT-35-turbo |
| Google AI | 云端 | 是 | Gemini 2.0 Flash/Pro, Gemini 1.5 Flash/Pro |
| Google Vertex AI | 云端 | 是 | 通过GCP访问Gemini模型 |
| AWS Bedrock | 云端 | 是 | Claude 3.5, Llama 3.1, Amazon Nova |
| xAI Grok | 云端 | 是 | Grok-2-latest, Grok-beta, Grok-vision-beta |
| Mistral AI | 云端 | 是 | Mistral-large, Mistral-small, Codestral |
| Groq | 云端 | 是 | Llama 3.3 70B, Llama 3.1 8B, Mixtral 8x7B |
| Cerebras | 云端 | 是 | Llama 3.3 70B, Llama 3.1 8B/70B |
| Cohere | 云端 | 是 | Command-r-plus, Command-r, Command |
| DeepInfra | 云端 | 是 | Llama 3.3/3.1, Mistral-small |
| Together AI | 云端 | 是 | Llama 3.3/3.1, Mistral, Qwen 2.5 |
| Perplexity | 云端 | 是 | Sonar系列模型（在线/聊天） |
| OpenRouter | 云端 | 是 | 多提供商访问（Claude, GPT-4, Gemini, Llama） |
| GitHub Copilot | 云端 | 是 | GPT-4o, GPT-4o-mini, o1-preview, o1-mini |
| Ollama | 本地 | 否 | Gemma 3/4, Llama 3.1/3.2, CodeLlama, Qwen 2.5, DeepSeek |
| LM Studio | 本地 | 否 | 任意本地模型 |
| OpenAI兼容 | 自定义 | 可选 | 任意OpenAI兼容端点 |

## 工具系统（30+工具）

### 文件操作
- **Read** - 读取文件内容，支持行范围
- **Write** - 创建/覆盖文件
- **Edit** - 精确查找替换，带diff输出
- **Glob** - 快速文件模式匹配（遵循.gitignore）
- **Grep** - 跨文件正则搜索
- **LS** - 列出目录内容

### 代码智能
- **LSP** - 语言服务器协议集成
- **Git** - Git操作（status, diff, log, blame）
- **Bash** - 执行shell命令，支持流式输出

### 网络与搜索
- **WebSearch** - 搜索网络信息
- **WebFetch** - 获取网页内容
- **SearchAndDownloadPapers** - 搜索学术论文

### 参考文献管理
- **DownloadReference** - 下载单个PDF参考文献
- **BatchDownloadReferences** - 批量下载参考文献
- **ReferenceManager** - 管理参考文献库

### 任务管理
- **TodoWrite** - 管理任务列表
- **Taskkill** - 终止运行中的任务
- **Batch** - 并行执行多个工具
- **Agent** - 派生子代理并行工作

### Notebook支持
- **NotebookWrite** - 写入Jupyter notebook单元格
- **NotebookRead** - 读取notebook内容

### 系统与工具
- **Cron** - 计划任务
- **Memory** - 存储和检索信息
- **Hook** - 配置钩子

## 斜杠命令

### 模型与提供商管理
| 命令 | 描述 | 示例 |
|------|------|------|
| `/model` | 显示当前模型和可用模型 | `/model` |
| `/model <name>` | 切换到指定模型 | `/model gpt-4o` |
| `/model <1-N>` | 通过序号选择模型 | `/model 1` 或 `/model #3` |
| `/model <provider>/<model>` | 切换提供商和模型 | `/model ollama/gemma3:27b` |
| `/model -l` | 列出所有提供商的所有模型 | `/model -l` |
| `/model -p` | 列出所有提供商 | `/model -p` |
| `/provider` | 显示当前提供商 | `/provider` |
| `/provider <name>` | 切换到不同提供商 | `/provider ollama` |

### 会话管理
| 命令 | 描述 |
|------|------|
| `/help` | 显示可用命令 |
| `/exit` | 退出OpenLaoKe |
| `/clear` | 清除屏幕和对话 |
| `/resume` | 恢复上次会话 |
| `/compact` | 压缩对话以节省上下文 |

### 配置
| 命令 | 描述 |
|------|------|
| `/permission [mode]` | 更改权限模式（default/auto/bypass） |
| `/settings` | 显示当前设置 |
| `/theme [name]` | 更改颜色主题 |
| `/cwd [path]` | 显示或切换工作目录 |

### 信息
| 命令 | 描述 |
|------|------|
| `/cost` | 显示会话费用和使用量 |
| `/usage` | 显示详细使用统计 |
| `/commands` | 显示示例命令 |
| `/doctor` | 诊断配置问题 |
| `/hooks` | 管理钩子 |
| `/mcp` | 管理MCP服务器 |

### 高级功能
| 命令 | 描述 |
|------|------|
| `/hyperauto` | 启动HyperAuto模式（自主运行） |
| `/skill <name>` | 执行技能 |
| `/memory` | 管理持久化内存 |
| `/agents` | 管理子代理 |

## 安装

```bash
# 克隆并安装
git clone https://github.com/cycleuser/OpenLaoKe.git
cd OpenLaoKe
pip install -e .

# 或使用uv（推荐）
uv pip install -e ".[dev]"
```

## 使用方法

### 首次运行
```bash
# 首次运行显示配置向导
openlaoke

# 重新配置
openlaoke --config
```

### 命令行选项
```bash
# 非交互模式
openlaoke "写一个排序列表的Python脚本"

# 指定模型和权限
openlaoke -m gpt-4o -p auto
openlaoke --provider ollama -m llama3.2

# 使用代理
openlaoke --proxy http://127.0.0.1:7890

# 设置工作目录
openlaoke --cwd /path/to/project

# 恢复上次会话
openlaoke --resume
```

### 模型选择

#### 交互式选择
```
OpenLaoKe: /model
Current provider: aliyun_coding_plan
Current model: glm-5

Available models (aliyun_coding_plan):
  [1] qwen3.5-plus
  [2] kimi-k2.5
  [3] glm-5 (current)
  [4] MiniMax-M2.5
  [5] qwen3-max-2026-01-23
  [6] qwen3-coder-next
  [7] qwen3-coder-plus
  [8] glm-4.7

Usage:
  /model <name>        - Switch to specific model
  /model <1-8>         - Select by index number
  /model #<1-8>        - Select by index (with # prefix)
  /model <provider>/<model> - Switch provider and model
  /model -l            - List all models from all providers
  /model -p            - List all providers
```

#### 快速切换示例
```bash
# 按名称切换
/model gpt-4o

# 按序号切换
/model 1
/model #3

# 同时切换提供商和模型
/model ollama/gemma3:27b
/model anthropic/claude-sonnet-4

# 仅切换提供商
/provider ollama
```

### 提供商配置

配置向导支持：
- **存储配置复用** - 检测并提供使用现有API密钥
- **环境变量** - 自动检测环境中的API密钥
- **多配置文件** - 配置多个提供商并在之间切换

```
Step 1: Choose your AI provider

   [1]   Anthropic                   needs setup
   [2]   OpenAI (GPT-4)              needs setup
   [3]   MiniMax                     ✓ stored
   [4]   Aliyun Coding Plan          ✓ stored
   [19]  Ollama (Local)              ✓ local
   [20]  LM Studio (Local)           ✓ local
   [21]  OpenAI-Compatible (Custom)  ✓ stored

Select provider [1-22] (19): 4

Configuring aliyun_coding_plan

   [1]  Stored config  Key: sk-sp-f9...0e3f, Model: glm-5
   [2]  Reconfigure    Enter new API key and settings

Select configuration source [1/2] (1): 1
✓ Using stored configuration for aliyun_coding_plan
```

## 高级功能

### HyperAuto模式

完全自主运行，具备自我改进能力：

```bash
/hyperauto on
/hyperauto --mode autonomous
/hyperauto --timeout 3600
```

功能特性：
- **自动任务分解** - 将复杂任务分解为子任务
- **自我验证** - 验证完成度和质量
- **自适应学习** - 从失败中学习并改进
- **技能生成** - 按需创建新技能
- **项目初始化** - 分析并设置新项目

### 任务监督

自动重试和完成验证：

- **需求解析** - 从用户请求中提取可验证的需求
- **进度监控** - 跟踪完成百分比
- **质量检查** - 反AI检测、参考文献验证
- **自动重试** - 带具体反馈的重试
- **升级处理** - 自动恢复失败时提醒

### 模型评估

基于模型能力的自适应任务分解：

**层级系统：**
- **第1层（高级）**：Claude 4, GPT-4o - 复杂任务，最小验证
- **第2层（能力强）**：Claude 3.5 Haiku, GPT-4o-mini, Gemma3 27B - 中等复杂度
- **第3层（中等）**：Gemma3 12B, Llama 3.1 8B, Qwen 2.5 14B - 有限子任务
- **第4层（基础）**：Gemma3 4B, Llama 3.2 3B - 原子操作，频繁验证
- **第5层（受限）**：Gemma3 1B, Llama 3.2 1B - 非常简单的任务，逐步指导

**自动适应：**
```python
# 小模型（gemma3:1b）- 任务分解为原子步骤
Task: "写一篇文章并创建图表"
分解后：
  Step 1: 写一篇文章
  Step 2: 创建图表
验证频率: every_step（每步验证）
最大子任务数: 4
重试限制: 8

# 高级模型（claude-sonnet-4）- 作为单个任务处理
Task: "写一篇文章并创建图表"
分解后: [单个任务]
验证频率: minimal（最小验证）
最大子任务数: 20
```

### 反AI检测

确保生成内容看起来像人类撰写：

**检测模式：**
- 没有实质内容的编号列表
- 没有证据的模糊声明
- 通用短语（"系统可以启用："）
- 缺乏具体引用
- 缺少技术深度

**强制要求：**
- 必须有可下载PDF的真实引用
- 必须有具体的数字和度量
- 代码引用必须带行号
- 完整段落，不要碎片化列表
- 技术深度（说明如何以及为什么，不只是做什么）

### 参考文献下载

学术写作自动下载PDF：

```
OpenLaoKe: 写一篇关于LLM效率的学术论文

[自动下载参考文献到pdf/目录]
✓ Downloaded: attention-is-all-you-need.pdf
✓ Downloaded: llama-2-open-foundation.pdf
✓ Downloaded: mixtral-of-experts.pdf

[正在撰写论文，带正确引用...]
```

命令：
```
/download-ref <URL>           - 下载单个参考文献
/download-refs <URLs...>      - 下载多个参考文献
/search-papers <query>        - 搜索并下载论文
```

### 技能系统

基于YAML的技能，用于专业工作流：

**可用技能（38+）：**
- `/academic-writer` - 学术论文写作
- `/browse` - 用于QA测试的无头浏览器
- `/qa` - 系统性QA测试和bug修复
- `/debug` - 根本原因调查的系统性调试
- `/design-review` - 视觉QA和设计打磨
- `/ship` - 发布工作流（合并、测试、创建PR）
- `/retro` - 每周工程回顾
- `/office-hours` - YC风格创业咨询
- `/brief-write` - 简洁写作风格
- `/humanizer` - 人性化AI生成的文本
- `/power-iterate` - 持续自主迭代
- `/skill-refiner` - 改进和完善技能

**使用方法：**
```bash
# 使用技能
/browse https://example.com

# 列出所有技能
/skill --list

# 获取技能帮助
/skill academic-writer --help
```

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

## 架构

```
openlaoke/
├── core/                      # 核心系统
│   ├── state.py              # 集中式状态管理
│   ├── tool.py               # 工具基类和注册表
│   ├── task.py               # 任务生命周期管理
│   ├── multi_provider_api.py # 多提供商API客户端
│   ├── repl.py               # REPL交互循环
│   ├── config_wizard.py      # 配置向导
│   ├── supervisor/           # 任务监督系统
│   ├── model_assessment/     # 模型能力评估
│   ├── hyperauto/            # HyperAuto模式
│   ├── skill_system.py       # 技能管理
│   └── memory/               # 持久化内存
├── tools/                    # 工具实现（30+）
├── commands/                 # 斜杠命令（20+）
├── types/                    # 类型定义
├── services/                 # 外部服务（MCP）
├── components/               # UI组件（TUI）
├── utils/                    # 工具函数
├── hooks/                    # 钩子实现
└── entrypoints/              # CLI入口点
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行代码检查
ruff check .
ruff check . --fix

# 格式化代码
ruff format .

# 类型检查
mypy

# 运行测试
pytest
pytest --cov
pytest tests/test_tools.py::TestBashTool::test_simple_command

# 构建包
python -m build
```

## 配置

用户配置存储在 `~/.openlaoke/config.json`：

```json
{
  "providers": {
    "active_provider": "ollama",
    "active_model": "gemma3:1b",
    "providers": {
      "ollama": {
        "api_key": "",
        "base_url": "http://localhost:11434/v1",
        "default_model": "gemma3:1b",
        "enabled": true
      }
    }
  },
  "proxy_mode": "none",
  "proxy_url": "",
  "max_tokens": 8192,
  "temperature": 1.0,
  "theme": "dark"
}
```

会话文件存储在 `~/.openlaoke/sessions/`

## 贡献

欢迎贡献！请：

1. Fork本仓库
2. 创建特性分支（`git checkout -b feature/amazing-feature`）
3. 提交更改（`git commit -m 'Add amazing feature'`）
4. 推送到分支（`git push origin feature/amazing-feature`）
5. 创建Pull Request

## 许可证

GPLv3