# 基准测试：提供商格式、本地模型与外壳对比

本文档记录用于验证 OpenLaoKe 提供商层、并把它与 [pi](https://github.com/earendil-works/pi)
作为外壳进行对比的全部实测。测试在本机进行，覆盖 6 个本地 Ollama 模型与 10 种语言。

所有结果都产自同一台机器，并保留足够细节以便复跑。小模型的数字噪声很大，请当方向性参考，不要当权威结论。

## 环境

| 项目 | 值 |
|------|----|
| 机器 | macOS（Apple Silicon），本机 |
| Python | 3.12（conda 环境 `dev`） |
| OpenLaoKe | 0.1.40 |
| pi | 0.85.1 |
| Ollama | 0.34.2，服务地址 `http://127.0.0.1:11434` |
| 本地端点 | `http://127.0.0.1:11434/v1`（OpenAI 兼容） |

参测的可对话模型（Ollama）。参数/量化/能力均取自 `ollama show` 原样输出：

| 模型 | 参数 | 量化 | 能力 |
|------|-----:|------|------|
| `qwen3.5:2b` | 2.3B | Q8_0 | completion, vision, tools, thinking |
| `qwen3.5:0.8b` | 873.44M | Q8_0 | completion, vision, tools, thinking |
| `LiquidAI-dev/lfm2.5-2.6b:latest` | 2.7B | Q4_K_M | completion, tools, thinking |
| `LiquidAI/lfm2.5-350m:latest` | 354.48M | Q8_0 | completion, tools, thinking |
| `lfm2.5-thinking:latest` | 1.2B | Q4_K_M | completion, tools, thinking |
| `granite4:350m-h` | 340.33M | Q8_0 | completion, tools |

全部六个模型都出现在下表中。日常使用已把本机模型缩减为两个 ≥2B 的模型
（`qwen3.5:2b`、`LiquidAI-dev/lfm2.5-2.6b`）；被删模型的数据仍保留在此。

> **注意**：思考型模型必须给足 `max_tokens`，否则配额会全花在思考上、可见答案为空。
> 语言测试用 `max_tokens=1200`，工具测试用 `2000`。

## 第一部分 —— 提供商格式兼容性

OpenLaoKe 需要同时说 OpenAI 与 Anthropic（Claude）两种格式，两者都做了端到端验证。

| 测试 | 端点 | 结果 |
|------|------|------|
| OpenAI 格式，非流式 | `POST https://api.deepseek.com/v1/chat/completions` | ✅ 返回 `PONG` |
| OpenAI 格式，流式 | 同上 | ✅ 流式返回 `PONG` |
| Anthropic 格式，真实端点 | `POST https://api.anthropic.com/v1/messages`（无效 key） | ✅ 请求正确；标准 401 `authentication_error` |
| Anthropic 格式，完整请求/响应 | 本地 mock | ✅ PASS |
| 本地 OpenAI 兼容 | `POST http://127.0.0.1:11434/v1/chat/completions` | ✅ 返回 `PONG` |

Anthropic mock 校验的是精确契约，而不只是连通性：

- 路径 `/v1/messages`
- 请求头 `anthropic-version: 2023-06-01`
- 请求头 `x-api-key`
- 请求体字段 `model`、`messages`、`max_tokens`、`temperature`、`system`
- 响应解析：`content[0].text == "PONG"`，用量 `input=11, output=2`

本地端点不再要求 API key：当 base URL 是本地地址（`localhost`、`127.0.0.1`、`0.0.0.0`、`::1`、
`host.docker.internal`）且未配置 key 时，OpenLaoKe 会发一个占位 bearer token。

## 第二部分 —— 本地模型能力（OpenLaoKe）

每个对话模型先用一句简单提示走 OpenLaoKe 的 OpenAI 兼容客户端，再走完整 agent 循环做文件任务
（“创建 `out.txt` 内容为 `hello pi`，然后运行 `cat out.txt`”）。

| 模型 | 非流式 | 流式 | 工具调用 | 备注 |
|------|:------:|:----:|:--------:|------|
| `qwen3.5:2b` | ✅ | ✅ | ✅ | 综合最好 |
| `qwen3.5:0.8b` | ✅ | ✅ | ✅ | 写成 `hello pi.`（多一个句号） |
| `LiquidAI-dev/lfm2.5-2.6b` | ✅ | ✅ | ✅ | 写成 `hello pi.`（多一个句号） |
| `LiquidAI/lfm2.5-350m` | ✅ | ✅ | ✅ | 文件内容正确 |
| `lfm2.5-thinking` | ✅ | ✅ | ❌ | 只思考不行动 |
| `granite4:350m-h` | ✅ | ✅ | ❌ | 工具调用幻觉报错 |

纯 embedding 模型（`nomic-embed-text`、`snowflake-arctic-embed`、两个 `all-minilm`、
`granite-embedding`）在 `/chat/completions` 上被正确拒绝（HTTP 400）——它们不是对话模型，
故不列入下表。

**第二部分中发现并修复的 bug。** Ollama 的 OpenAI 兼容流把思考放在 `delta.reasoning`，
而 DeepSeek 用 `delta.reasoning_content`。OpenLaoKe 原本只读后者，导致思考型模型流式输出为空。
现在两个字段都会读取。

## 第三部分 —— 多语言一致性：OpenLaoKe vs pi

让两个外壳各用 10 种语言回答“用一句话介绍你自己”，再对回复做语言分类：
按字符脚本判定（Hangul → 韩语；假名 → 日语；CJK → 中文；西里尔 → 俄语），
拉丁字母则按停用词特征判断。`OK` 表示检测到的语言与请求一致。

### 配置

- **OpenLaoKe：**
  `python -m openlaoke --provider openai_compatible --base-url http://127.0.0.1:11434/v1 --api-key not-needed --model <m> --max-tokens 1200 "<提示词>"`
- **pi：** 在 `~/.pi/agent/models.json` 中声明 `ollama-local` 提供方
  （`api: openai-completions`、`compat.supportsDeveloperRole=false`、
  `compat.supportsReasoningEffort=false`）；调用方式
  `pi -p --provider ollama-local --model <m> --no-skills --no-context-files --no-extensions --no-prompt-templates --no-themes "<提示词>"`

### OpenLaoKe

| 模型 | 中 | 英 | 日 | 法 | 俄 | 德 | 西 | 葡 | 意 | 韩 | 得分 |
|------|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|-----:|
| `qwen3.5:2b` | OK | OK | OK | OK | OK | OK | OK | OK | OK | OK | 10/10 |
| `qwen3.5:0.8b` | OK | OK | OK | OK | OK | zh | OK | OK | OK | en | 8/10 |
| `LiquidAI-dev/lfm2.5-2.6b` | OK | OK | OK | OK | en | OK | OK | OK | OK | OK | 9/10 |
| `LiquidAI/lfm2.5-350m` | en | OK | OK | OK | OK | OK | OK | OK | es | OK | 8/10 |
| `lfm2.5-thinking` | en | OK | OK | OK | en | en | OK | en | en | OK | 5/10 |
| `granite4:350m-h` | empty | OK | en | ? | en | en | en | OK | en | en | 2/10 |

### pi

| 模型 | 中 | 英 | 日 | 法 | 俄 | 德 | 西 | 葡 | 意 | 韩 | 得分 |
|------|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|-----:|
| `qwen3.5:2b` | OK | OK | OK | OK | OK | OK | OK | OK | es | OK | 9/10 |
| `qwen3.5:0.8b` | empty | OK | OK | OK | OK | OK | OK | OK | OK | OK | 9/10 |
| `LiquidAI-dev/lfm2.5-2.6b` | OK | OK | zh | OK | OK | OK | OK | es | OK | OK | 8/10 |
| `LiquidAI/lfm2.5-350m` | OK | OK | OK | OK | OK | OK | OK | en | OK | OK | 9/10 |
| `lfm2.5-thinking` | en | OK | en | en | OK | en | OK | en | en | en | 3/10 |
| `granite4:350m-h` | en | OK | en | OK | en | en | en | OK | es | en | 3/10 |

### 合计

| 外壳 | 通过 |
|------|-----:|
| OpenLaoKe | **42/60** |
| pi | 41/60 |

各语言通过数（两个外壳合计，满分 12）：

| 语言 | 通过 | 语言 | 通过 |
|------|-----:|------|-----:|
| 英 | 12/12 | 葡 | 8/12 |
| 法 | 10/12 | 韩 | 8/12 |
| 西 | 10/12 | 德 | 7/12 |
| 日 | 8/12 | 中 | 6/12 |
| 俄 | 8/12 | 意 | 6/12 |

## 结论

1. **瓶颈不在外壳。** OpenLaoKe（42/60）与 pi（41/60）基本打平，差异在模型噪声范围内。
   同一个模型在两个外壳里表现几乎一致。
2. **模型选择才是决定性的。** `qwen3.5:2b` 在两个外壳拿到 10/10 和 9/10；
   `granite4:350m-h` 与 `lfm2.5-thinking` 都只有 2–5/10。
3. **外壳影响的是“身份”，不是语言。** 同一个模型在 OpenLaoKe 里答“我是 OpenLaoKe……”，
   在 pi 里答“我是 Pi Coding Agent……”，说明系统提示词确实生效，但没有改变回复语言。
4. **过小的模型不适合 agent 场景。** `granite4:350m-h` 在 OpenLaoKe 里产生工具幻觉、乱建文件；
   外壳的管道是对的，是模型不行。

## 说明与局限

- 语言分类器是启发式的。`?`、`es`、`zh` 等可能代表混语言回复或分类边界，不一定是硬失败。
- 每格只跑了 1 次。小模型本身随机性大，重跑会移动个别格子。
- 两处异常：`pi + qwen3.5:0.8b + 中文` 超时 420s（空回复）；
  `openlaoke + granite4:350m-h + 中文` 空回复。
- 对所有模型，英文都是最强语言，中文/意大利语最弱。这是模型属性，与两个外壳无关。

## 复现

```bash
# 1. 提供商格式（OpenAI 路径需要 DeepSeek key；Anthropic 路径用本地 mock 校验）
python scripts/bench_provider_formats.py

# 2. 本地模型能力与工具调用
python scripts/bench_local_models.py --base-url http://127.0.0.1:11434/v1

# 3. 多语言，双外壳
python scripts/bench_harness_multilang.py
```

模型列表、提示词与语言分类器的具体实现见 `scripts/` 下对应脚本。
