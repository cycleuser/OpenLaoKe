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
| edit（含 `multiedit`） | `Edit` + `ApplyPatch` | P11 | **已实现**（`Edit` 有 `replace_all`；一次多处、跨文件改写由 `ApplyPatch` 承担并保证全或无，不再单设 `multiedit` 别名） |
| apply_patch | `ApplyPatch` | P11 | **已实现**（Codex `*** Begin Patch` 信封与 unified diff 两种格式；先在内存里校验全部 hunk，全部通过才落盘；越界路径、已存在的新增、缺失的更新一律拒绝） |
| agentgrep（grep/find/outline） | `Grep` 三模式 | P3 | **已实现**（find 按名匹配、outline 列定义、grep 结果标注所属定义、paths_only、max_regions） |
| bash | `Bash` | — | 已有，P7 补后台化与超时接管 |
| todo | `Todo` + `/todos` | P4 | **已实现**（phase/lane/after/completely_blocked/external_blocker/assessment，done 必须带 evidence，否则降级 in_progress） |
| bg | `Bg` | P7 | **已实现**（list/status/output/tail/wait/watch/cancel；日志落文件，output 支持 offset 续读，wait/watch 不靠轮询） |
| batch | `Batch` | P8 | **已实现**（1-10 并发、禁止嵌套、默认关闭，`config.enable_batch` 或 `/batch on` 打开；破坏性工具一律拒绝，因为批内调用绕过交互式授权） |
| webfetch | `WebFetch` | P12 | **已实现**（httpx + stdlib HTMLParser，去脚本样式、抽标题、按 max_chars 截断，不引新依赖） |
| websearch | `WebSearch` | P12 | **已实现**（DuckDuckGo HTML 端点，无需 key；解析 title/url/snippet，失败时明确说没解析到而不是编结果） |
| memory | `Memory` + `/memory` | P9 | **已实现**（remember/recall/search/list/forget/tag/link/related/stats；`core/memory_store.py` 每项目一个 JSON，BM25 检索、中文按字二元切分；系统提示里只注入 id 与摘要，正文靠 recall 取） |
| session_search | `SessionSearch` | P10 | **已实现**（BM25 扫描 ~/.openlaoke/sessions，可按 days/cwd/role 过滤，回 session id + 消息序号 + 时间 + 摘要） |
| conversation_search | `ConversationSearch` | P10 | **已实现**（检索当前会话全部消息，压缩掉的内容也能找回来） |
| skill_manage | `InvokeSkill` + `/skill` | P16 | **已实现**（list / install <github-url> [name] / remove / reload / activate / `info <name>` / `off <name>` / clear；安装走 `core/skill_installer.py`，支持 skills.json 索引、`skills/` 目录扫描与 OpenCode `index.json` 协议） |
| mcp | MCP 桥接 + `/mcp` | P13 | **已实现**（`core/mcp_client.py` stdio JSON-RPC：initialize/tools/list/tools/call；`core/mcp_runtime.py` 把服务端工具注册成 `mcp__server__tool`，带 intent 与结果账本；启动失败只记进 `/mcp` 不阻塞会话；`enable_mcp` 与 `mcp_servers` 生效） |
| codemode | `CodeMode` | P14 | **已实现**（`core/code_sandbox.py`：独立解释器 `python -I -B`、环境变量清空、open 限定工作区、屏蔽进程/网络/FFI 模块与 os.system、CPU/内存 rlimit、超时杀进程、输出上限；文档写明这不是对抗恶意代码的边界） |
| swarm | `Swarm` | P15 | **已实现**（`core/swarm.py`：最多 6 条泳道并发跑子代理，start 立即返回、await 带超时、status 看状态与结果、note/messages 共享板、cancel 收尾；`contextvars` 记当前泳道，Write/Edit/ApplyPatch 的每次落盘都记进触碰台账并归属到具体 worker） |
| panel / side_panel | `Panel` | P17 | **已实现**（`core/panel_render.py` 自带一个小 markdown 子集渲染器与内联 CSS，输出单文件 HTML，raw HTML 先转义、javascript: 链接不生成；可 `open_in_browser`） |
| open | `Open` | P17 | **已实现**（仅 http(s) URL 与工作区内路径，其他 scheme 与越界路径一律拒绝；按平台用 open/xdg-open/start） |
| browser | `Browser` | P18 | **可选扩展**（需 `enable_browser=true` 且 selenium 可导入，二者缺一就不注册；open/text/links/script 四个动作；缺依赖时报清楚原因并建议用 WebFetch） |
| jcode_docs | `OpenLaoKeDocs` | P16 | **已实现**（list/search/read，检索 `docs/` 与根目录 README/CHANGELOG/AGENTS，按标题切段后 BM25 排序，read 可只取某一节） |
| schedule | `Schedule` + `/schedule` | P18 | **已实现**（`core/scheduler.py`：every/daily/一次性三种写法，条目可排队提示或跑后台命令，JSON 持久化；循环默认关，`enable_scheduler` 打开；会话关着不触发） |
| compile_remote | `Compile` | P16 | **已实现**（白名单 latexmk/pdflatex、pandoc、typst、py_compile；在源文件目录内执行、带超时、报告产物与新文件，缺哪个二进制就点名哪个；改成本地执行，不把文档送去远端） |
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
| 三套 agent 循环合一 | 自定 | P1 | **部分实现**（`core/engine.py` 提供 `run_loop`/`EnginePolicy`/`execute_tool` 与统一的消息整形；`agent_runner` 与 `cli._run_non_interactive` 已迁入，子代理的 `tool_result` 旧格式一并修正；REPL 保留流式外壳但复用同一套消息与工具结果形状） |
| 会话上下文上限 / effective_budget | HARNESS.md:87 | P2 | **已实现**（2b85890） |
| token 账本用真实 usage | token-accounting-reliability.md | P2 | **已实现** |
| 结果账本：内容去重 + 超大先扣住 | agentgrep + accept_large_output | P3 | **已实现**（`core/result_ledger.py`，重复内容换指针，超 1500 token 先摘要并报价，`accept_large_output` 才发全文） |
| todo 策略：自动续跑预算 3 次、清单变化重置、完成置信度 | jcode-todo-policy、TODO_FOLLOWUP_CONFIGURATION.md | P4 | **已实现**（`core/todo_engine.py` + `repl._todo_auto_continue`；blocked 条目不消耗预算） |
| 命令风险四级（safe/low/confirm/catastrophic） | jcode-command-risk | P5 | **已实现**（`utils/permissions/command_risk.py` 按爆炸半径判定，Bash 新增 `justification` 入参，catastrophic 硬拒且 justification 解不开，low 放行并留痕） |
| 安全两层权限（无 always-deny） | SAFETY_SYSTEM.md:83 | P5 | 待做 |
| 软中断：生成中入队、安全点注入 | SOFT_INTERRUPT.md | P6 | 部分（已有输入队列，补 urgent 标记与安全点） |
| 生命周期钩子 8 键 + 独立超时 + pre_tool 闸门 + post_tool_feedback | HOOKS.md:8 | P6 | **已实现**（19 个扩展点，新增 turn_start/turn_end/tool_gate/tool_feedback，旧名 pre_tool/post_tool/pre_tool_transform/post_tool_feedback 为别名；每个钩子可设 timeout_ms，async 钩子用 asyncio.wait_for 截断并计入 stats；tool_gate 在权限检查之前可否决，tool_feedback 的文本入输入队列交给模型） |
| 工具超时自动转后台（auto_background_timeout_ms=3000） | TOOL_BACKGROUND_TIMEOUT.md | P7 | **已实现**（`Bash` 超过阈值即转后台并返回 task id，显式 timeout 才杀进程；日志写文件，不再按块 `_persist`） |
| 编辑统计（增删行，按会话落盘） | SESSION_EDIT_STATS.md | P7 | **已实现**（`core/edit_stats.py` 用序列比对算真实增删行，Write/Edit 记账，`/edits` 查看，随会话持久化） |
| 计划图上限 MAX_PLAN_ITEMS=1024 | jcode-plan | P15 | **已实现**（`core/todo_engine.py:MAX_PLAN_ITEMS`，超出时拒绝新增并回一条 warning） |
| swarm 输出预算 | jcode-swarm-core | P15 | **已实现**（`Swarm.report(max_chars=4000)` 按泳道均分，单条超长截断并注明，整份再兜一次上限） |
| KV cache 监视与未命中分类 | HARNESS.md:131 | P6 | **已实现**（`core/cache_monitor.py`：按 model/system/tools/历史消息做前缀指纹，排除最新一条避免每轮误报；读 provider 的 cache_read/cache_creation 与 OpenAI 的 prompt_tokens_details.cached_tokens；`/cache` 报告命中率、前缀是否变化、连续未命中） |
| schema 方言集中归一 | jcode-schema-dialect | P3 | 部分（已有 schema 消毒，要集中成一层） |
| 会话级环境变量（作业快照） | HARNESS.md:3-86 | P7 | **已实现**（`AppState.snapshot_env/set_env_var/unset_env_var`；每个作业在启动时取一次快照，之后改会话变量不影响已运行作业） |
| 会话休眠释放派生缓存 | SESSION_HIBERNATION.md | P19 | **已实现（单进程等价物）**：`/sleep` 释放记忆索引、缓存读数、swarm 板与任务句柄并 gc；有泳道在跑时拒绝执行；各类存储下次用到时自行从磁盘重建 |
| 模糊匹配（空白容差） | jcode-fuzzy | P16 | **已实现**（`utils/fuzzy.py`：先精确，再逐行忽略行尾空白，最后把连续空白归一后匹配；命中位置按区间替换，并在结果里注明是哪一档，`replace_all` 与模糊匹配组合会被拒绝） |
| 终端图片协议（kitty/sixel/iterm2） | jcode-terminal-image | P17 | 待做（纯 Python 可实现 Kitty 协议） |
| 生产力仪表盘 | jcode-productivity-core | P20 | **Markdown 版已实现**（`scripts/productivity_report.py` 扫会话出逐日活动/项目分布/工具用量；另加 `/stats` 会话内仪表盘）。PNG 版本未做 |
| 开销门禁 | bench_startup.py 等 | P6 | **已实现**（`scripts/bench_startup.py`：冷解释器测入口模块导入耗时与峰值 RSS，超预算非零退出，可 `--max-ms/--max-mb/--json`；仓库无 CI，以脚本退出码当门禁） |

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
