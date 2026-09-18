# pi 设计对齐分析（OpenLaoKe 改进参考）

参考对象：pi（`@earendil-works/pi-coding-agent`），作者 Mario Zechner，仓库
`github.com/earendil-works/pi`，本地副本在 `~/Documents/GitHub/Others/pi`。

## 授权协议

- pi：MIT（`LICENSE`，Copyright (c) 2025 Mario Zechner）。
- OpenLaoKe：GPL-3.0-only。

结论：**MIT 与 GPLv3 兼容，可以把 pi 的代码并入 OpenLaoKe**。MIT 是宽松许可，
允许被 GPLv3 工程吸收；条件是：

1. 保留 pi 的 MIT 版权声明与许可全文（放在 `THIRD_PARTY_NOTICES.md` 或 `NOTICE`）。
2. 合并后的整体仍以 GPLv3 分发（OpenLaoKe 已是 GPLv3，无需改变）。
3. 若只是借鉴设计思路、不复制代码，则无版权义务；仅在直接引用 pi 源码时需要署名。

反向不成立：不能把 GPLv3 代码并入 MIT 工程。当前方向是安全的。

## pi 的核心设计思路

1. **极简内核 + 激进扩展**：默认只给 `read/write/edit/bash` 四个工具，其余全部通过
   TypeScript 扩展、技能、prompt 模板、主题、packages 提供。
2. **技能渐进披露**：系统提示词里只放技能名 + 描述（正文按需读取）。
3. **短系统提示词**：把每轮固定上下文压到很小（实测基线 ~1.5k token）。
4. **会话即树**：JSONL 树结构，`/tree` 原地分支、`/fork`、`/clone`，压缩保历史。
5. **用户 prompt 模板**：`~/.pi/agent/prompts/*.md`，`/name` 展开，支持 `$1`/`$@`/
   `${1:-default}`/`${@:N:L}` 参数。
6. **多运行模式**：交互、print、JSON、RPC、SDK。
7. **package 分发**：扩展/技能/模板/主题打包成 npm/git 包共享。
8. **默认不做**：MCP、子智能体、权限弹窗、plan 模式、内置待办——全部按需自建。

## OpenLaoKe 现状对照

| pi 设计点 | OpenLaoKe 现状 | 结论 |
|---|---|---|
| 极简内核 + 扩展 | 32 个工具 + 15 钩子，功能丰富 | 已覆盖，钩子即扩展点 |
| 技能渐进披露 | `InvokeSkill` meta-tool + 运行时读取 SKILL.md | **已对齐**（思路不同但等价）|
| 短系统提示词 | `SYSTEM_PROMPT_STATIC` ~3.5k 字符 + `CacheGuard` 前缀缓存 | 基本对齐 |
| 会话树 | `SnapshotStore` + fork/branch/rewind（CHANGELOG 已记录） | 已覆盖 |
| **用户 prompt 模板** | **无** | **缺口，本次已补** |
| print/JSON/RPC 模式 | Web UI + FastAPI server，缺 `--print`/`--json` | 缺口 |
| package 分发 | `skill_installer.py`，无统一 package 清单 | 部分 |
| 默认不做 MCP 等 | 默认开着 MCP、子智能体、plan、权限 | 设计取向不同，可不改 |

## 改进行动

### 已完成（本次）

- `openlaoke/core/prompt_templates.py`：pi 风格 prompt 模板系统。
  发现路径 `~/.openlaoke/prompts/`、`.openlaoke/prompts/`（非递归），
  支持 `description`、`argument-hint` frontmatter 与 `$1`/`$@`/`$ARGUMENTS`/
  `${1:-default}`/`${@:-default}`/`${@:N}`/`${@:N:L}` 参数替换。
- `tests/test_prompt_templates.py`：21 个用例，`pytest` 全过，`ruff` 通过。

尚未接线（避免与当前分支 WIP 冲突），后续在 `openlaoke/commands/registry.py`
注册一个 `/prompt <name> [args]` 命令即可：

```python
from openlaoke.core.prompt_templates import expand_prompt_template, list_prompt_templates
```

### 建议后续

1. **非交互模式**（P1）：新增 `openlaoke -p/--print "<prompt>"` 与 `--json`，便于脚本化、
   回归测试和 CI。pi 的 print/JSON 模式是这套设计里最实用的部分。
2. **prompt 模板接线**（P1）：注册 `/prompt` 命令，并在 REPL 输入以 `/` 开头且命中模板名时自动展开。
3. **package 清单**（P2）：为技能/模板定义统一 manifest，支持从 git/npm 一键安装。
4. **技能描述常驻**（P2，需权衡）：pi 把全部技能名+描述放进系统提示词；OpenLaoKe 目前只在
   `[session context]` 块里透出，且缺描述。可考虑加一个「可用技能」精简列表，帮助模型发现技能，
   代价是每轮固定 token 增加（实测每个技能约 210 token）。

## 附：实测数据（同模型同任务）

pi 与 opencode（同类 harness）在同一 `deepseek-chat`、同一任务下的对照，用于理解
「固定基线」与「技能规模」的成本结构：

- 固定基线：pi ~1.5k token/请求，opencode ~7.3k token/请求。
- 每技能增量：约 210 token/技能（两者几乎相同）。
- 结论：差距来自固定基线，技能规模会成倍放大任务总 token（每轮重发上下文）。

OpenLaoKe 的 `InvokeSkill` meta-tool 设计在技能很多时比 pi 更省，值得保留。
