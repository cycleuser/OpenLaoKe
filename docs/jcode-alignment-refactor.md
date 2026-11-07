# jcode 设计对齐分析（OpenLaoKe 重构方案）

参考对象：jcode（`github.com/1jehuang/jcode`），Rust 实现的编码智能体外壳，本地副本
`~/Documents/GitHub/Others/jcode`，核对提交 `ad6843ab`（2026-11-07，`Cargo.toml` 版本 0.99.1）。
本文所有 OpenLaoKe 行号以提交 `5c01a8a`（v0.1.44）为准。

## 授权协议

- jcode：MIT（`LICENSE`，Copyright (c) 2025 Jeremy Huang）。OpenLaoKe：GPL-3.0-only。
- 与 pi 的结论相同（见 `docs/pi-design-alignment.md`）：**MIT 可以并入 GPLv3**，方向安全。
  直接移植代码需把 MIT 声明追加到 `THIRD_PARTY_NOTICES.md`；只借鉴设计思路、不复制代码，无版权义务。
- jcode 是 Rust，OpenLaoKe 是 Python，实际能搬的是**接口形状与策略**，不是代码本身。
  本文所有条目按"借鉴设计"写，不产生引用义务。

## 结论先说

pi 的极简设计把大量责任交给模型：工具少而直白，提示词短，靠模型自己规划、自己推进、自己发现做错了。
这个前提在前沿模型上成立，在本地 4B–14B 上不成立。OpenLaoKe 现在的状态是**用 pi 的内核外形，
加一层补丁式的小模型兜底**：689 行的 `small_model_optimizations.py` 加上散在 `repl.py` 各处的话术，
能跑，但策略和循环缠在一起，谁也测不透。

jcode 值得学的不是 Rust、不是常驻服务端、也不是那 28 个工具，而是四件把它和别的外壳区分开的事：

1. **上下文当成有读数的预算**，不是估算完就忘的字符数；
2. **工具结果按"模型已经看过什么"裁剪**，重复内容不再重发；
3. **任务状态做成数据结构**，于是能自动续跑、能标记"彻底阻塞"、能要求完成证据；
4. **开销本身进 CI 预算**，启动时间和内存是回归门禁，不是文档里的一句话。

这四条对小模型的收益比对大模型更大，因为它们补的正是弱模型缺的那部分：自查、推进、节制。

## 基线（本机实测，2026-11-08）

```bash
DEV=/Users/fred/miniconda3/envs/dev/bin/python
$DEV -m pytest              # 153 passed in 2.35s
$DEV -m ruff check .        # All checks passed
$DEV -m ruff format --check .   # 6 files would be reformatted（基线就不干净）
$DEV -m mypy openlaoke      # Found 6 errors in 4 files（AGENTS.md:16 的 `python -m mypy` 会报缺目标，
                            #   pyproject.toml:71 的 [tool.mypy] 没有 files 配置）
```

重构期间这三条必须**只降不升**；`ruff format --check` 那 6 个文件在 P0 里一次格式化掉，
之后要求 0。

## 现状诊断

### A 类：现在就错着的（P0 全清）

| # | 位置 | 事实 | 后果 |
| --- | --- | --- | --- |
| A1 | `core/cache_guard.py:469` | 导入不存在的 `openlaoke.agent.context` | 带 `user_input` 调 `build_compact_prompt` 直接 `ImportError` |
| A2 | `core/cache_guard.py:477` | 导入不存在的 `openlaoke.core.distilled_templates` | 同上，mypy 已报 |
| A3 | `core/hook_system.py:129` | `v2` 属性导入不存在的 `openlaoke.hooks.lifecycle`，`openlaoke/hooks/` 目录整个不存在 | 首次访问 `v2` 就抛，README 宣传的扩展点有一部分是空的 |
| A4 | `core/repl.py:466` + `cli.py:174,270` | 主循环硬编码 `max_iterations = 100`，从不读 `app_state.max_steps`（`state.py:90`） | `--max-steps` 是死配置 |
| A5 | `core/repl.py:678` | `streaming_supported = True` 硬赋常量，`:687` 起约 140 行非流式分支永不执行 | 死代码，误导后续改动 |
| A6 | `core/tool_call_parser.py` | 369 行全仓零引用（已 grep 核实，含 tests） | 与 `repl.py:1449` 的 `_parse_inline_tool_calls` 功能重复 |
| A7 | `AGENTS.md:47` | 文档说会话是 JSONL，实际 `state.py:202` 是整文件覆盖写 JSON | 文档与实现不一致 |
| A8 | `openlaoke/skills/` | 空目录 | 包数据噪音 |

A1/A2/A3 是同一类问题：**代码引用了不存在的模块**。这类问题的共同成因是这三条路径没有测试覆盖，
P0 除了修，还要给每条补一个冒烟测试。

### B 类：架构债（P1–P4 处理）

1. **三套 agent 循环并存**：`core/repl.py:465` `_run_api_loop`（1764 行文件里）、
   `core/agent_runner.py:101` `run_subagent`（`max_iterations=50`）、
   `entrypoints/cli.py:288` `_run_non_interactive`（`max_iterations=50`）。
   剪枝、重试、只读并发、去重守卫、小模型修正，三处各自一份或干脆没有：非交互模式既不剪枝也不重试。
   任何修复要做三遍，这是重构的第一目标。
2. **压缩框架有一半没接线**：运行时只 import 了 `compact/fast_pruner`（`repl.py`、`commands/base.py`），
   `compactor.py`、`strategies.py`（4 种策略）、`summarizer.py`、`token_budget.py:110` 的
   `TokenUsageTracker` 全仓无调用方。也就是说 `trigger_threshold=0.8` 那套配置完全没生效。
3. **token 估算原始且到处散**：`fast_pruner.py:208,380,417,490` 一律 `len(content) // 4`，
   中文按字符数算严重低估；提供商返回的真实 usage 从不回灌校准。
4. **没有会话级上下文上限**：只有累计统计（`state.py:61` `token_usage`），
   没有"这个会话允许用多少"这一维，界面也就无法显示准确的剩余量。
   本地模型窗口来自 `model_discovery.py:230` 的 `get_effective_context_limit`，这个是对的，缺的是上面那层。
5. **工具结果没有"已看过"裁剪**：唯一防重复是"同参数调用超 3 次报警"（`repl.py:927-948`），
   换个参数重搜同一区域照样把整片内容再塞一遍。
   全局兜底只有 `truncate_tool_history` 的 **4096 字节**头尾截断（`tool.py:419`，`repl.py:1250` 调用）。
   本地 8K 窗口下，同一份 grep 结果重复三次就吃掉一半窗口。
6. **搜索工具不带结构信息**：`tools/grep_tool.py:28` 只提供 `context` 行数（`rg -C` 风格），
   模型要判断"命中处在哪个函数、这个函数多长"就得整读文件，一次 Read 就是几千 token。
   `strategies.py:293` 的 `MicroCompactStrategy` 有 dedupe 逻辑，但它没接线，等于没有。

## jcode 侧值得移植的六件事

jcode 事实来源：`docs/HARNESS.md`（章节行号：会话上下文上限 :87、Token optimization :125、
KV cache :131、Todo 规划层级 :139、彻底阻塞 :191、泳道内实时状态 :212、可爬坡性度量 :218）、
`https://jcode.sh/tool-schema.json`（2026-11-07 快照，28 个内置工具）。

### 1. 会话级上下文上限与准确预算

`docs/HARNESS.md:87` 的做法：`set_context_cap` 设会话上限，返回 `effective_budget` =
模型窗口与会话上限里较小者；可以高于也可以低于全局默认，但不得超过模型窗口；`0`/`null` 清除；
调低上限不打断当前请求、不立刻改写历史，只对后续请求生效。事件的 `token_usage` 里带
`effective_budget`，界面据此画进度条，而不是把模型标称窗口当可用量。

移植到 OpenLaoKe：新增 `core/context_budget.py`，把 `repl.py:613-623` 的阈值算式收进去。
弱模型这边窗口常常只有 8K–32K，一个"还剩多少"的准确读数能直接避免过早或过晚剪枝，
这比任何压缩算法都值钱。

### 2. 结构感知的搜索工具

`docs/HARNESS.md:125`：agentgrep 的匹配结果带上文件结构（命中的是哪个函数、函数在哪一行），
让模型不必读整个文件就能理解周边；并且**结果按这个智能体已经看过什么做裁剪**。
`tool-schema.json` 里 agentgrep 有 `mode`（grep/find/outline/trace）、`paths_only`、
`max_regions`、`accept_large_output`。

移植：替换 `tools/grep_tool.py`，输出加符号名与定义范围；再加自适应裁剪层。
这一条对弱模型的价值最高——弱模型最常见的浪费就是"搜到了，再读整个文件确认"。

### 3. 工具结果层：去重、指针化、过大先扣住

综合 jcode 两个做法：`agentgrep` 的"已见裁剪"，加上它 28 个工具统一的 `accept_large_output`：
超大结果先不发，报出代价，模型再决定是否接受。
注意 jcode 的 batch 是**并行执行独立调用**，而 OpenLaoKe 已经在循环里自动并发了多个只读调用
（`repl.py:886-909`），这条不用照搬。

移植：新增 `core/result_ledger.py`，做三件事——内容寻址去重（重复内容换成指针）、
超过阈值的结果先返回摘要加代价、把"续取"变成显式参数而不是让模型自己拼分页。

### 4. 任务分层 + 自动续跑 + 完成证据

jcode 是 phases → lanes → items 三层，lane 可以声明依赖前面哪些具体任务而不必等整个阶段收工
（`docs/HARNESS.md:139`）；`completely_blocked` 是未完成条目上的一个状态，要填理由，
自动续跑会跳过它但不影响同泳道其它条目（`:191`）。它的实测数据是 Terminal-Bench 2.1 上
来得及做完的试验通过率 92% 对 88%。

移植（弱模型版，去掉 swim/泳道的复杂度）：单层任务清单，每条带
`status`/`attempts`/`blocked_reason`/`evidence`；模型无工具调用但清单还有未完成项时自动唤醒继续，
有次数上限；标完成必须给验证证据（跑了什么、输出是什么）。
这条直接治弱模型两个老毛病：半途停下等人回话、以及"我觉得做完了"其实没验证。

### 5. 意图字段 `intent`

jcode 全部 28 个工具的 `input_schema` 都把 `intent` 列为必填，界面在同一行显示它。
它不省 token（每个调用多几十字符），换来每一步都留了一条可读的动机记录，弱模型跑偏时能看出它当时想干什么。

移植：`core/tool.py:66` 的 `Tool` 基类统一注入一个 `intent: str = Field(...)`，工具实现忽略它，
循环与界面消费它。改动小，但要重新冻结 schema 与系统提示词前缀。

### 6. 开销进 CI 预算

jcode 有 `scripts/bench_startup.py`（分项毫秒预算：help 20ms、服务端就绪 80ms、冷启动 150ms）、
`scripts/bench_headless_memory.py`（进程树 PSS 而非 RSS）、`docs/MEMORY_BUDGET.md`（硬上限与
"棘轮期望"两套预算，并写明目标是让内存变化可度量、可审、回归必须带解释地更新文档和测试）。

移植：`scripts/bench_startup.py` 与 `scripts/bench_memory.py`（Python 版，量 import 到首屏的耗时、
以及每多一个会话的 RSS 增量），阈值写进 `pyproject.toml`，超了 CI 红。
Python 这边更要卡这条，因为 `openlaoke` 的 import 时间对本地小模型用户体验很敏感。

## 不移植的（以及为什么）

| jcode 特性 | 不移植的理由 |
| --- | --- |
| 单 daemon 多会话（`docs/SERVER_ARCHITECTURE.md`） | Python 单用户 CLI 拿这套收益小、代价大：要处理套接字权限、重载、跨平台守护进程，而省内存的前提是同时开很多会话。真要省内存，P4 的模型卸载与结果裁剪更直接。 |
| batch 嵌套调用（`tool_calls` 数组） | 弱模型在嵌套 JSON 结构上失败率明显更高，而 `repl.py:886` 已经由 harness 自动并发只读调用，省轮次的目的已经达到，不该把这个负担转嫁给模型。 |
| swarm 与同目录文件冲突检测 | 多智能体协调依赖强模型的规划与自持能力，弱模型做协调者只会放大错误。OpenLaoKe 现有的 `agent_runner.run_subagent` 保持"一次性子任务"定位即可。 |
| self-dev 改自身源码 | 审计面从"我允许哪些插件"变成"这次改了哪几行"，与弱模型的可控性目标相反。 |
| Jev 远程相关性判定替代嵌入检索 | OpenLaoKe 主要面向本地模型场景，记忆内容不应外发。跨会话记忆走本地关键词检索（阶段 5），不引入外部判定调用。 |
| KV cache 冷通知 | 本地 Ollama/LM Studio 无提供方缓存语义，只有 Anthropic/OpenAI 路径用得上；`cache_guard.py` 的双 `cache_control` 标记保留即可，先不做监视器。 |

## 分阶段实施计划

每阶段独立提交、独立可回滚，收尾标准统一：`pytest` 全绿、`ruff check` 无错、
`ruff format --check` 无待格式化文件、`mypy openlaoke` 错误数 ≤ 基线（6）。

### P0：卫生与止损（0.5 天，纯删与修，无行为变更）

- 修 A1/A2：删掉两处指向不存在模块的导入，或补出最小实现（倾向删，因为 `build_compact_prompt`
  目前不需要它们），并为 `build_compact_prompt` 带/不带 `user_input` 各补一个测试。
- 修 A3：`openlaoke/hooks/lifecycle.py` 要么补出来，要么把 `v2` 属性连同 README 里那部分宣传一起去掉。
- 修 A4：`max_iterations` 改成读 `app_state.max_steps`；补一个"传 `--max-steps 2` 时确实在两轮后停"的测试。
- 修 A5：`streaming_supported` 死分支删除或改成真实探测；P0 倾向删非流式分支（若某提供商路径依赖它，
  改成配置项而不是硬编码常量）。
- 修 A6：删 `core/tool_call_parser.py`（全仓零引用已核实），其能力由 `repl.py:1449` 承担。
- 修 A7/A8：`AGENTS.md:47` 会话格式说明改成实际格式；删空目录 `openlaoke/skills/`。
- 顺手：`$DEV -m ruff format .` 清掉那 6 个文件。

不做的事：不改任何提示词文字（会破坏 Anthropic 前缀缓存），不动会话文件格式。

### P1：三套循环合一（1–1.5 天）

新增 `core/engine.py`，把唯一一份循环放进去：

```python
@dataclass(slots=True)
class EngineConfig:
    max_turns: int = 100
    prune: bool = True
    retry: bool = True
    parallel_readonly: bool = True
    auto_continue: int = 0          # P4 才用，先占位

@dataclass(slots=True)
class EngineResult:
    stop_reason: Literal["no_tool_calls", "max_turns", "guard", "error"]
    turns: int
    usage: TokenUsage

class AgentEngine:
    def __init__(self, api, registry, state, budget, *, config: EngineConfig) -> None: ...
    async def run(self, messages, *, on_event: EventSink | None = None) -> EngineResult: ...
```

- `repl.py` 退化为渲染 + 输入 + 事件消费，调 `engine.run(..., on_event=...)`；
- `agent_runner.py` 删掉自己的循环，用 `max_turns=50, auto_continue=0` 的配置跑同一引擎；
- `entrypoints/cli.py:_run_non_interactive` 同样改成 `prune=True, retry=True` 的同一引擎，
  非交互模式从此也有剪枝和重试。
- 现在散在 `repl.py:554-585`、`:811-834`、`:876-884` 的小模型话术先**原样搬进引擎**并标注来源行号，
  到 P4 再抽成策略层，避免一次改动两件事。

新增 `tests/test_engine.py`，至少覆盖：无工具调用即停、`max_turns` 生效、只读并发与写调用顺序、
瞬态错误重试后消息序列合法、guard 触发时 `stop_reason == "guard"`、子代理与交互模式产出一致的事件序列。

风险提示：这是 P0–P6 里唯一一处"行为面可能变"的改动，务必先补 characterization 测试再动。

### P2：token 账本与会话级上限（1 天）

新增 `core/context_budget.py`：

```python
@dataclass(frozen=True)
class ContextBudget:
    model_window: int
    session_cap: int | None
    global_cap: int | None
    effective_budget: int        # min(窗口, 会话上限或全局上限)
    used_tokens: int
    source: Literal["provider_usage", "estimate"]
```

- 估算换成 CJK 感知启发式（中日韩字符 1 字≈1 token，ASCII 4 字符≈1 token），
  有 provider usage 时优先用真实值并回灌校准；`fast_pruner.py:208,380,417,490` 的 `len()//4` 全部换掉。
- `effective_budget` 语义照 jcode：会话上限可高可低但不得超窗口，`0` 清除，换模型时重算但不丢覆盖。
- 加 `/context` 命令输出窗口、会话上限、有效预算、当前用量与估算来源；界面进度条改读 `effective_budget`。
- 剪枝阈值继续用现有 `keep_tail = max(2048, ctx_budget // 3)`，但基数换成 `effective_budget`。
- 未接线的 `compact/strategies.py`、`summarizer.py`、`token_budget.py` 在这一阶段**明确处置**：
  要么接线要么删除，不许继续半死不活（倾向删除，`fast_pruner` 已经够用且 <5ms）。

### P3：结果账本与结构感知搜索（1.5 天，收益最大）

新增 `core/result_ledger.py` + 改造 `tools/grep_tool.py`：

```python
class ResultLedger:
    def record(self, tool: str, args: dict, content: str) -> ToolResultBlock:
        """内容与哈希已存在时返回指针块；超过阈值时返回摘要加代价说明。"""

    def seen(self, content: str) -> str | None: ...
```

- grep 输出加符号信息：纯 stdlib 正则索引 `def`/`class`/`func`/`fn` 等常见声明，
  **不引入 tree-sitter 依赖**（要引需你点头，见文末待定）。
- 同一会话内重复出现的内容块换成 `"(内容与第 N 次调用相同，已省略 X token)"`，
  指针可被后续请求解引用（保留原内容在 ledger 里，不进上下文）。
- 单次工具结果超过阈值（默认 1500 token）先返回头尾摘要加代价与续取提示，模型显式要求才给全文
  （对应 jcode 的 `accept_large_output`）。
- `Glob` 与 `ListDirectory` 保持不动，不做工具合并，避免破坏已有会话与提示词（见文末待定）。

### P4：任务引擎与话术收拢（1 天）

- 新增 `tools/todo_tool.py`（第 10 个工具）：`items` 带 `name`/`status`/`attempts`/
  `blocked_reason`/`evidence`，`status ∈ {pending, in_progress, done, blocked}`。
- 引擎侧自动续跑：清单里仍有非 `blocked` 未完成项且模型无工具调用时唤醒继续，
  上限用 `EngineConfig.auto_continue`（默认 2，弱模型别放太开），唤醒话术带当前未完成项清单。
- `done` 必须带 `evidence`（命令与关键输出），缺失时降级为 `in_progress` 并回问一句。
- 新增 `core/small_model_policy.py`：把 `repl.py` 里所有小模型话术与
  `small_model_optimizations.py:667` 的 `get_small_model_guidance`、`:573` 的
  `apply_structured_thinking_prefix` 收成 `policy_for(model_size) -> PromptPolicy`，
  循环只问策略要文本，不再自己判断体型。

### P5：本地跨会话记忆（可选，1 天）

用现成的空桩 `repl.py:174` `_register_memory_hooks()` 与 `:535` 的 `memory_prompt`：
纯本地关键词检索（BM25，纯 Python，无新依赖），条目存 `~/.openlaoke/memory/*.md`，
字段含 `valid_from`/`valid_to`/`supersedes`，检索在本机完成，不外发任何内容。

### P6：开销门禁（0.5 天）

`scripts/bench_startup.py`：量 `python -c "import openlaoke"`、首次渲染、端到端首字；
`scripts/bench_memory.py`：`tracemalloc` + 子进程 RSS，报"每多一个会话的增量"；
预算写进 `pyproject.toml`，超阈值退出码非零，接进 CI（jcode 的 PSS 思路在 Python 侧用
`tracemalloc` 近似，说明口径差异）。

## 全程硬约束

1. **系统提示词字节稳定**：`core/cache_guard.py` 冻结前缀是为了 Anthropic 缓存命中，
   P1–P4 任何阶段不得改动提示词文字与工具 schema 顺序。需要改时集中到一次提交，
   并在 CHANGELOG 注明会断一次缓存。
2. **会话格式向后兼容**：`AppState._persist()`（`state.py:202`）读到旧格式必须能加载。
   真要迁 JSONL 放到重构之后单独一轮，`version` 字段已有（`sessions.py:27`）。
3. **不加隐式依赖**：`pyproject.toml` 的运行依赖目前有 pydantic、rich、prompt_toolkit、httpx、
   pyyaml、chardet、pathspec 七项，P0–P6 全部用 stdlib 实现（含 token 估算与正则索引）。
4. **`AGENTS.md:85` 那条约束需要改写**：现文是"保持 pi 对齐：新增功能优先用技能 / prompt 模板 /
   扩展点，而不是往内核堆工具"。P4 要往内核加 `todo` 工具、P3 要在内核加结果账本，
   与这条直接冲突。建议改成：pi 对齐是默认取向，但可靠性机制（上下文预算、结果账本、任务状态）
   允许进内核。
5. 每阶段一次提交，提交信息带阶段号；`CHANGELOG.md` 各加一条。

## 验收清单

- [ ] `pytest` 用例数从 153 增至 ≥ 200，全绿，总耗时 < 5s
- [ ] `mypy openlaoke` 错误数 6 → 0（P0 顺手清 A1/A2 那两条）
- [ ] `ruff check` 与 `ruff format --check` 双 0
- [ ] `core/repl.py` 从 1764 行降到 900 行以内，agent 循环只剩一份
- [ ] 同一会话里重复搜索的第二次调用，工具结果 token ≤ 首次的 20%
- [ ] `grep` 输出含符号名与定义范围，且默认路径下无新增第三方依赖
- [ ] `--max-steps` 有测试证明生效
- [ ] `bench_startup.py` 与 `bench_memory.py` 进 CI，超阈值红

## 需要你定的四件事

1. **搜索工具是否合并**：把 `Grep`/`Glob`/`ListDirectory` 合成一个 agentgrep 式工具更省 token，
   但工具名变化会让已有会话与提示词模板失效。我的建议是先只增强 `Grep`，不合并。
2. **是否允许新依赖**：结构感知搜索若上 tree-sitter 精度明显更好，纯正则对不常见语言会漏。
   默认按"不加依赖"做。
3. **系统提示词冻结破例几次**：P4 加 `todo` 工具、P5 加记忆都必然动 schema 与提示词。
   建议攒到最后一次改，中间阶段用不变 schema 的能力实现。
4. **阶段顺序**：我的建议 0 → 1 → 2 → 3 → 4 → 6 → 5。前三阶段就能改变弱模型的实际表现；
   记忆放最后，因为它对单轮任务成功率影响最小。

确认这四点后我按阶段开始提交。
