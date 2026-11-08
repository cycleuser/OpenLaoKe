# jcode 全量功能对照与实现进度（OpenLaoKe）

参考对象 jcode：`github.com/1jehuang/jcode`，本地副本 `~/Documents/GitHub/Others/jcode`，
核对提交 `ad6843ab`（2026-11-07，Cargo 版本 0.99.1，MIT）。
规模：89 个 crate、28 个模型可见工具、137 个斜杠命令、147 篇文档、200+ 脚本。
本文是"全部实现"的清单与台账：每一项都要么已实现、要么排在某个阶段，不允许静默丢失。

设计前提不变（见 `docs/jcode-alignment-refactor.md`）：OpenLaoKe 面向本地小模型，
移植时凡是把结构负担推给模型的机制，都改成外壳代做或默认关闭的形态。

## 一、无法等价实现的部分（先说清楚，不含糊）

| jcode 功能 | 为什么不能等价 | OpenLaoKe 的处置 |
| --- | --- | --- |
| cloud / remote / ssh 会话托管（`CLOUD_*`、`NATIVE_SSH`、`REMOTE_COMPILE`） | 依赖 jcode 自有云端与订阅额度，无公开协议 | 不实现云端。`compile_remote` 改为本地沙箱编译（隔离临时目录 + 超时 + 资源上限），接口名保留 `Compile` |
| Gmail / Calendar / 邮件回复审批 | 需要 Google OAuth 与网络外发，主场景是本地模型 | 做成可选扩展（`openlaoke.ext.gmail`），默认不注册；未配置时工具不出现在列表里 |
| Azure 凭据、Copilot/Grok/Cursor/Antigravity 订阅反代 | 各家私有鉴权流程，且与本项目"自带 API Key"定位无关 | 不实现。已有的 Anthropic/OpenAI/Google/Bedrock/Cohere/Ollama/LM Studio 路径保持 |
| 桌面伴侣、macOS computer use、移动端、iOS app、语音 | 需要系统级权限与原生组件 | 不实现。桌面相关只保留 `open`（open / xdg-open / start） |
| TUI 动画、mermaid 渲染、donut 计时器、视觉自调试 | ratatui 专用，OpenLaoKe 是 rich + prompt_toolkit | 不实现动画。mermaid 改为可选 `dot`/`mmdc` 外部命令渲染 PNG |
| QuickJS 代码模式（`codemode`） | 需要嵌入 JS 引擎 | 改为 Python 受限执行沙箱（P14），能力等价：脚本式串联多个工具、并发、暂存 |
| 单守护进程多会话（`SERVER_ARCHITECTURE`） | 收益在多会话常驻场景，改动波及快照/信号/Windows | 推迟到 P19，且做成本地 HTTP + Unix socket 的可选服务层，不改默认单进程模型 |

其余全部纳入下面的阶段表。

## 二、工具层（28 个 → OpenLaoKe）

| jcode 工具 | OpenLaoKe | 阶段 | 状态 |
| --- | --- | --- | --- |
| read | `Read` | — | 已有 |
| write | `Write` | — | 已有 |
| edit（含 `multiedit` 别名） | `Edit` | P11 | 已有，补 replace_all 与多替换原子性 |
| apply_patch（含 `patch` 别名） | `ApplyPatch` | P11 | 待做（Codex `*** Begin Patch` + unified diff） |
| agentgrep（grep/find/outline） | `Grep` 三模式 | P3 | **已实现**（find 按名匹配、outline 列定义、grep 结果标注所属定义、paths_only、max_regions） |
| bash | `Bash` | — | 已有，P7 补后台化与超时接管 |
| todo | `Todo` | P4 | 待做（phases/lanes/items、`completely_blocked`、`external_blocker`、评估字段） |
| bg | `Bg` | P7 | 待做（list/status/output/tail/cancel/wait/watch） |
| batch | `Batch` | P8 | 待做（1-10 并发、禁止嵌套、默认关闭，靠配置开） |
| webfetch | `WebFetch` | P12 | 待做 |
| websearch | `WebSearch` | P12 | 待做（可配后端，未配置不注册） |
| memory | `Memory` | P9 | 待做（remember/recall/search/list/forget/tag/link/related，本地 BM25） |
| session_search | `SessionSearch` | P10 | 待做 |
| conversation_search | `ConversationSearch` | P10 | 待做 |
| skill_manage | `InvokeSkill` + `/skills` | — | 已有，P16 补 manage 子命令 |
| mcp | `Mcp` | P13 | 待做（配置里已有 `mcp_servers`，运行时没接） |
| codemode | `CodeMode` | P14 | 待做（Python 受限沙箱） |
| swarm | `Swarm` | P15 | 待做（泳道 worker、消息、`await_members`、文件触碰通知） |
| panel / side_panel | `Panel` | P17 | 待做（终端内 markdown 面板 → 落 HTML 供浏览器打开） |
| open | `Open` | P17 | 待做 |
| browser | `Browser` | P18 | 可选扩展，需 selenium，默认不注册 |
| jcode_docs | `OpenLaoKeDocs` | P16 | 待做（读 `docs/`） |
| schedule / end_ambient_cycle / schedule_ambient | `Schedule` | P18 | 待做（本地计划任务，ambient 默认关） |
| compile_remote | `Compile` | P16 | 待做（本地隔离编译） |
| gmail / calendar | 可选扩展 | P20 | 默认不注册 |
| selfdev / desktop_selfdev | 不做 | — | 明确不移植（审计面过大，与弱模型可控性相反） |
| maintainainer_feedback | 不做 | — | 反馈改为 GitHub issue 流程 |
| integration_tools（赞助发现） | 不做 | — | 商业注入，无技术价值 |
| debug_socket / sdk | `sdk` 事件出口 | P19 | 部分（引擎事件流已可被外部消费） |
| initiative（jcode 里已注销） | 不做 | — | 上游自己也停用 |

所有工具的公共入参 `intent`（schema 里必填，本地校验不惩罚缺失，避免弱模型白白吃一次重试）与 `accept_large_output` 已在 P3 由 `core/tool.py:with_common_fields` 统一注入，界面在工具行尾显示 intent。

## 三、机制层

| 机制 | jcode 出处 | OpenLaoKe 阶段 | 状态 |
| --- | --- | --- | --- |
| 会话上下文上限 / effective_budget | HARNESS.md:87 | P2 | **已实现**（2b85890） |
| token 账本用真实 usage | token-accounting-reliability.md | P2 | **已实现** |
| 结果账本：内容去重 + 超大先扣住 | agentgrep + accept_large_output | P3 | **已实现**（`core/result_ledger.py`，重复内容换指针，超 1500 token 先摘要并报价，`accept_large_output` 才发全文） |
| todo 策略：自动续跑预算 3 次、gate digest、完成置信度 | jcode-todo-policy、TODO_FOLLOWUP_CONFIGURATION.md | P4 | 待做 |
| 命令风险四级（Safe/Low/Confirm/Catastrophic） | jcode-command-risk | P5 | 待做（现有 classifier 两级，要扩成四级 + justification） |
| 安全两层权限（无 always-deny） | SAFETY_SYSTEM.md:83 | P5 | 待做 |
| 软中断：生成中入队、安全点注入 | SOFT_INTERRUPT.md | P6 | 部分（已有输入队列，补 urgent 标记与安全点） |
| 生命周期钩子 8 键 + 独立超时 + pre_tool 闸门 + post_tool_feedback | HOOKS.md:8 | P6 | 待做（现有 hook_system 键名不同，要对齐） |
| 工具超时自动转后台（auto_background_timeout_ms=3000） | TOOL_BACKGROUND_TIMEOUT.md | P7 | 待做 |
| 编辑统计（增删行，按会话落盘） | SESSION_EDIT_STATS.md | P7 | 待做 |
| 计划图上限 MAX_PLAN_ITEMS=1024 | jcode-plan | P15 | 待做 |
| swarm 输出预算（报告 4000 字、尾部 1000 token） | jcode-swarm-core | P15 | 待做 |
| KV cache 监视与未命中分类 | HARNESS.md:131 | P6 | 待做 |
| schema 方言集中归一 | jcode-schema-dialect | P3 | 部分（已有 schema 消毒，要集中成一层） |
| 会话级环境变量（替换而非合并，作业快照） | HARNESS.md:3-86 | P7 | 待做 |
| 会话休眠释放派生缓存 | SESSION_HIBERNATION.md | P19 | 待做（单进程下等价物是释放快照与索引） |
| 模糊匹配（替换/换位/加权） | jcode-fuzzy | P16 | 待做 |
| 终端图片协议（kitty/sixel/iterm2） | jcode-terminal-image | P17 | 待做（纯 Python 可实现 Kitty 协议） |
| 生产力仪表盘（扫会话出 Markdown+PNG） | jcode-productivity-core | P20 | 待做（Markdown 版） |
| 开销门禁进 CI | check_*_budget.py、bench_startup.py、memory_regression_gate.sh | P6→P20 | 待做 |

## 四、命令层

137 个命令不做等量搬运，按能力去重后归到六组，逐组补齐（现有 39 个）：

- 会话与历史：`/rewind /fork /clone /resume /sessions /rename /save /unsave /clear /new /export /import /transcript /catchup /back` — P10
- 模型与提供商：`/models /model-status /effort /fast /transport /provider-test-coverage /cache` — P12
- 上下文与开销：`/context`（已做）、`/usage /compact /thinking /reasoning /tool-call-details` — P2/P6
- 任务与并行：`/todos /poke /plan /swarm /agents /subagent /subagent-model /review /judge /autoreview /autojudge` — P4/P15
- 记忆与技能：`/memory /skills` — P9/P16
- 诊断与维护：`/info /version /changelog /config /log /keys /diff /screenshot /reload /doctor` — P16

## 五、阶段顺序

P3 结果账本 + AgentGrep + intent/accept_large_output（1.5 天）
P4 Todo 引擎与 todo-policy（1 天）
P5 命令风险四级 + 两层权限（1 天）
P6 钩子对齐 + KV cache 监视 + 开销门禁脚本（1 天）
P7 Bg 工具 + 超时自动后台 + 编辑统计 + 会话环境变量（1 天）
P8 Batch（默认关闭）+ 引擎并发统一（0.5 天）
P9 本地记忆工具与 BM25 检索（1 天）
P10 会话与对话检索 + 会话命令组（1 天）
P11 ApplyPatch 与 Edit 多替换（0.5 天）
P12 WebFetch / WebSearch 与模型命令组（0.5 天）
P13 MCP 运行时（1 天）
P14 CodeMode 受限沙箱（1 天）
P15 Swarm 与计划图（1.5 天）
P16 文档/模糊匹配/Compile/杂项命令（1 天）
P17 Panel / Open / 终端图片（1 天）
P18 Schedule 与可选扩展（1 天）
P19 可选服务层与会话休眠（1.5 天）
P20 生产力仪表盘与文档收尾（0.5 天）

## 六、验收台账

每阶段收尾必须：`pytest` 只增不减、`ruff check` 0、`ruff format --check` 0、`mypy openlaoke` 0（P0 后基线为 0）。
本文件随实现进度更新，工具与机制表的"状态"列是唯一口径。
