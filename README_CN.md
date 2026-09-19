# OpenLaoKe

> 遵循 [pi](https://github.com/earendil-works/pi) 的设计、用 Python 实现的终端编程智能体 —— 极简、快速、可扩展。

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: GPLv3](https://img.shields.io/badge/license-GPLv3-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

## OpenLaoKe 是什么

OpenLaoKe **遵循 pi 的设计**，用 Python 实现。它保留了 pi 的核心想法——一个很小的、有主见的智能体循环，其余的由你自己扩展——然后把其它几乎所有东西都砍掉了。

- **9 个工具**，与 pi 的能力面一致：`Read`、`Write`、`Edit`、`Bash`、`Grep`、`Glob`、`ListDirectory`、`PowerShell`，外加用于按需加载技能的 `InvokeSkill`。
- **pi 的 23 个内置命令**，外加 prompt 模板与技能。
- **树状会话，支持 branch / fork / clone / rewind**，底层是追加写文件。
- **prompt 模板**（`/name` 与 `/prompt <name>`），支持 `$1`、`$@`、`${1:-default}`、`${@:N:L}`。
- **20+ 个提供商，原生协议对接** —— 直接说 Anthropic Messages、OpenAI Chat Completions、Google `generateContent`、AWS Bedrock 和 Cohere；其余（Azure、xAI、Mistral、Groq、OpenRouter、Copilot、Aliyun、MiniMax、OpenCode Zen）走 OpenAI 格式，本地服务（Ollama、LM Studio、vLLM）也一样。
- 约 1.9 万行 Python。没有 MCP、没有子智能体、没有计划模式、没有权限弹窗、没有后台 bash。

### 工具

| 工具 | 用途 |
|------|------|
| `Read` | 读文件（文本、图片、PDF） |
| `Write` | 新建或覆盖文件 |
| `Edit` | 精确的字符串替换修改 |
| `Bash` | 执行 shell 命令（流式输出） |
| `Grep` | 跨文件正则搜索 |
| `Glob` | 按模式查找文件 |
| `ListDirectory` | 列目录 |
| `PowerShell` | Windows 命令执行 |
| `InvokeSkill` | 运行时加载已安装的技能 |

### 斜杠命令

pi 的内置命令一一对应地实现了：

`/new` `/name` `/session` `/tree` `/fork` `/clone` `/compact` `/resume` `/export` `/import` `/copy` `/share` `/changelog` `/hotkeys` `/scoped-models` `/trust` `/login` `/logout` `/reload` `/model` `/thinking` `/settings` `/quit`

另有几个符合同样哲学的新增命令：`/prompt`（展开 prompt 模板）、`/skill`（列出或激活技能）、`/theme`、`/help`。

## 设计哲学

OpenLaoKe 是有意照 pi 的路子来的，而这份哲学本身就是重点：

**一、内核要小，能力向外长。** 默认的工具集小而稳定。新能力通过技能、prompt 模板、钩子，以及你自己的代码接入，而不是靠不断堆内置功能。内核小，才容易理清、启动快、运行便宜。

**二、速度由“固定上下文基线”决定。** 每一次请求都要重发系统提示词、工具定义和技能元数据。这份固定开销乘以每一个模型回合，就是延迟和成本的主项。功能多的助手，每一次调用都在为它交这笔钱。把基线压小，是一个设计决策，不是事后优化——见下面「速度与复杂度」。

**三、渐进披露。** 技能正文在未被调用前不进上下文。随提示词走的只有名字和简短描述，真正的指令等模型确实需要时再加载。

**四、会话是树，不是线。** 每个会话都是带父子链接的追加日志，所以可以原地分叉、克隆、回退，都不丢历史。

**五、有主见的"不做"。** pi 的原话是：*没有 MCP、没有子智能体、没有权限弹窗、没有计划模式、没有内置待办、没有后台 bash。* OpenLaoKe 继承这份清单。这些不是缺失的功能，而是"真正需要时你自己去搭"的功能。

**六、本地优先，能零成本。** 把 OpenLaoKe 指向你自己机器上的模型——一个 OpenAI 兼容端点是一等公民，不是备胎。

## 为什么改成按 pi 的方式设计

这一段是诚实的项目史，因为转向本身才是最有意思的部分。

OpenLaoKe 最初并没有按 pi 的方式来设计。它 2026 年 4 月起步时，是一个功能齐全、OpenCode 风格的助手：30+ 工具、MCP、子智能体、一个 supervisor、一个计划模式、权限系统、记忆、反 AI 检测层、双模型协作、Web UI、FastAPI 服务端……一路长到了大约 **78,000 行**、286 个模块。

然后我们做了测量。同一个模型、同一个任务，换不同的外壳去跑，结果显示：**每次请求的固定开销**（系统提示词加工具定义）才是压倒性的主项。在一次受控对比里，极简外壳的基线是每次请求约 1.5k token，而功能齐全的外壳约 7.3k。而每装一个技能，两边都大约增加 210 token——一模一样，因为两边都遵循同一套 Agent Skills 标准。结论不太舒服，但很清楚：

> 功能齐全的外壳所谓的"强大"，大部分是每一个回合都要交的固定税，换来的却是你常常用不到的功能。

于是我们做了决定：**保住那些我们引以为傲的工程，但采用那个能产生这些数字的设计。** 现在的 OpenLaoKe 采用 pi 的设计，用 Python 实现。

| | 之前 | 现在 |
|---|---:|---:|
| Python 文件 | 286 | **69** |
| 代码行数 | 77,955 | **19,349** |
| 运行时依赖 | 11 | **7** |
| 测试 | — | **147 通过** |
| 内置命令 | 40+ | **23（与 pi 对齐）** |

## 一段简史

这段历史要从仓库之外讲起。早在 **2024 年**，模型与外界交互的循环就已经开始做了，起点是 **[CLAP 系列项目](https://github.com/cycleuser/CLAP)**：本地对话的加载与续接、借助模型访问数据库、以及命令行方式的访问。那时还没有完整的工具调用实现，CLAP 比它更早——但正是这些项目，构成了后来的地基。

本仓库的代码从 2026 年 4 月开始。提交记录讲的是四个阶段的故事：**长大 → 专精 → 收敛 → 简化**。

**第一阶段——造引擎（2026 年 4 月）。** 首次提交落地了一个与提供商无关的智能体循环。它很快就长出了模型侧的机械：CPU/GPU 混合推理、智能模型选择、批量操作、双模型协作、模型预热、原子生成，以及 HyperAuto（一个自主的自我改进模式）。

**第二阶段——触到边缘（2026 年 4–5 月）。** 浏览器式的提供商认证（Chrome/Firefox）、`Ctrl+P` 模型选择器，以及很关键的一步——通过 llama-cpp-python 支持本地 GGUF 模型，让"零 API 成本"真正可用。随后是记忆工具和不断膨胀的工具集。

**第三阶段——收敛（2026 年 5–8 月）。** 各部分逐渐成熟：思考显示系统、带字节稳定前缀的缓存感知提示词引擎、`InvokeSkill` 元工具（无论装多少技能，工具定义都保持稳定）、会话中途切换显示语言，以及一个 OpenCode 风格的工作流内核——回退 / 分叉 / 分支，加上计划模式闸门。我们补上了架构图，也给那些被借鉴过的项目写上了公开致谢。依赖已经瘦身过一轮。

**第四阶段——简化（2026 年 9 月）。** 转向 pi 的设计。在上面那次测量之后，整个功能面被拿到同一个问题下重新审视：*pi 有这个吗？* 没有的，就离开默认路径。仓库从 7.8 万行降到 1.9 万行，工具从 30+ 降到 9 个，命令降到 pi 的 23 个。现在这份代码读起来，就像它所遵循的那套设计：小、清楚、快。

## 速度与复杂度

这里说的速度，是从按下回车到拿到答案的真实等待时间。它几乎完全由三件事决定。

**固定上下文基线。** 每一轮都要重发系统提示词、工具定义和技能元数据。极简外壳大约 1.5k token，功能重的外壳在还没算上用户那句话说，就可能越过 7k。在多轮任务里，这个数要乘以回合数。OpenLaoKe 的默认路径是刻意压在偏小一侧的。

**每个技能的开销。** 技能在被调用前只有元数据。实测下来，无论哪个外壳，每个技能大约占 210 token 的固定上下文，因为两边都遵循 Agent Skills 标准。启示是：技能数量线性放大成本，装你真正用的就好。

**回合数与工具往返。** 工具更少更利落，往返就更少。九个模型能一眼看懂的工具，胜过三十个它还得去分辨的工具。

复杂度是这笔交易的另一半。一个 1.9 万行、模块摊平的代码库，是你能装进脑子、能做安全审计、能放心扩展的体量。在我们看来，这份"看得懂"比一长串功能列表更值钱——也正是转向的原因。

## 会话

`~/.openlaoke/sessions/` 存放追加写的会话 JSON；`~/.openlaoke/snapshot/`（由 `SnapshotStore` 管理）按回合记录文件与对话状态。由此支持：

- `/tree` —— 列出已记录的回合，并回退到任意一个（代码 + 对话）
- `/fork [turn]` —— 在某个回合分叉，继承该点的历史
- `/clone` —— 在当前位置复制一份会话
- `/compact` —— 用纯算法的快速剪枝压缩上下文（不调用 LLM）

## 技能

技能遵循 [Agent Skills](https://agentskills.io) 标准：一个目录，里面放一个带 YAML frontmatter 和 Markdown 指令的 `SKILL.md`。

```text
~/.openlaoke/skills/<name>/SKILL.md   # 项目级：.openlaoke/skills/<name>/SKILL.md
```

只有名字和描述进系统提示词，正文在 `InvokeSkill` 被调用时才读取。`/skill` 可以列出已安装的技能并激活其中一个。

## prompt 模板

pi 风格的可复用 Markdown 提示词。在 `~/.openlaoke/prompts/review.md` 放一个文件，然后调用它：

```markdown
---
description: 审查暂存的改动
argument-hint: "<path>"
---
审查暂存的改动。先关注 $1，再看 ${2:-正确性}。
```

```text
/review src/app.py        # 或者：/prompt review src/app.py
```

支持的参数语法：`$1`、`$2`… 位置参数；`$@` / `$ARGUMENTS` 表示全部；`${1:-default}` 与 `${@:-default}` 表示默认值；`${@:N}` 与 `${@:N:L}` 表示切片。

## 快速开始

```bash
pip install openlaoke
openlaoke
```

需要 Python 3.11+。

### API key

设好 key 就能用：

```bash
export OPENAI_API_KEY=sk-...         # OpenAI
export ANTHROPIC_API_KEY=sk-ant-...  # Anthropic（Claude）
openlaoke --provider openai --model gpt-4o
```

### 本地模型

要用本地模型，你自己起一个 OpenAI 兼容的服务，把它指过去就行——怎么起是你的事。以 [Ollama](https://ollama.com) 为例：

```bash
ollama serve
ollama pull llama3.2

openlaoke --provider openai_compatible \
  --base-url http://127.0.0.1:11434/v1 \
  --api-key not-needed \
  --model llama3.2
```

本地端点不需要真的 API key。LM Studio（端口 1234）、vLLM，以及任何其它 OpenAI 兼容服务都一样。

### 提供商

原生协议：**Anthropic Messages**、**OpenAI Chat Completions**、**Google `generateContent`**、**AWS Bedrock** 与 **Cohere**。内置提供商：OpenAI、Anthropic（Claude）、Azure OpenAI、Google、Google Vertex、AWS Bedrock、xAI、Mistral、Groq、Cerebras、Cohere、DeepInfra、Together AI、Perplexity、OpenRouter、GitHub Copilot、MiniMax、Aliyun Coding Plan、OpenCode Zen。任何 OpenAI 兼容端点也都能用——Ollama、LM Studio、vLLM，或你自己的网关。

## 配置

`~/.openlaoke/config.json`：

```json
{
  "providers": {
    "active_provider": "ollama",
    "active_model": "llama3.2",
    "providers": {
      "ollama": { "base_url": "http://localhost:11434/v1", "default_model": "llama3.2", "enabled": true },
      "openai": { "api_key": "sk-...", "default_model": "gpt-4o", "enabled": false }
    }
  },
  "proxy_mode": "none",
  "max_tokens": 8192,
  "theme": "dark"
}
```

### 环境变量

`ANTHROPIC_API_KEY`、`OPENAI_API_KEY`、`GOOGLE_API_KEY`、`DEEPSEEK_API_KEY`、`MINIMAX_API_KEY`、`XAI_API_KEY`、`MISTRAL_API_KEY`、`GROQ_API_KEY`、`OPENROUTER_API_KEY`、`GITHUB_TOKEN`、`OPENLAOKE_MODEL`、`HTTP_PROXY` / `HTTPS_PROXY`。

## 架构

```text
openlaoke/
├── entrypoints/cli.py     # argparse CLI + 配置向导入口
├── core/
│   ├── repl.py            # 交互循环、流式输出、工具分发
│   ├── agent_runner.py    # 与提供商无关的智能体回合
│   ├── multi_provider_api.py
│   ├── sessions.py        # 会话持久化
│   ├── snapshot/          # 按回合的文件 + 对话快照
│   ├── compact/           # 快速剪枝 + 摘要
│   ├── skill_system.py    # Agent Skills 加载器
│   ├── prompt_templates.py
│   ├── hook_system.py     # 扩展点
│   └── tool.py            # Tool / ToolRegistry
├── tools/                 # read, write, edit, bash, grep, glob, ls, powershell, invoke_skill
├── commands/              # pi 命令集 + prompt/skill 命令
├── types/                 # 核心类型、提供商、钩子
└── utils/                 # 配置、主题、diff、路径安全
```

## 开发

```bash
pip install -e ".[dev]"
ruff check . && ruff format .
pytest
```

本地的 pytest 测试集覆盖 pi 兼容命令、prompt 模板、会话、快照、工具、diff 与 i18n。

## 基准测试

提供商格式验证、本地模型能力测试，以及双外壳（OpenLaoKe vs pi）在 6 个本地模型、10 种语言上的
对比，详见 [`docs/benchmarks_CN.md`](docs/benchmarks_CN.md)（中文）与
[`docs/benchmarks.md`](docs/benchmarks.md)（英文）。复现脚本在 [`scripts/`](scripts)。

## 致谢

OpenLaoKe 遵循 Mario Zechner 的 **[pi](https://github.com/earendil-works/pi)** 的设计，用 Python 实现。pi 采用 MIT 协议；OpenLaoKe 采用 GPLv3。

早期迭代还借鉴了以下项目的模式：

- **[nanobot](https://github.com/HKUDS/nanobot)** —— 事件驱动的智能体循环、AutoCompact
- **[smallcode](https://github.com/Doorman11991/smallcode)** —— 工具调用解析、写前先读保护
- **[OpenCode](https://github.com/opencode-ai/opencode)** —— 全屏 TUI、会话分叉/分支模型

## 协议

GPLv3。pi 采用 MIT，与 GPLv3 兼容；其版权声明保留在 `THIRD_PARTY_NOTICES.md` 中。
