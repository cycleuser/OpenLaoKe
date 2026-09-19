# 基准测试：提供商格式、本地模型与外壳对比

本文档记录用于验证 OpenLaoKe 提供商层、并把它与 [pi](https://github.com/earendil-works/pi)
作为外壳进行对比的全部实测。测试在本机进行，覆盖 6 个本地 Ollama 模型与 10 种语言。

所有结果都产自同一台机器，并保留足够细节以便复跑。小模型的数字噪声很大，请当方向性参考，不要当权威结论。

## 环境

| 项目 | 值 |
|------|----|
| 机器 | Apple M4（10 核 CPU），16 GB 内存，macOS |
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

全部六个模型都出现在下表中。日常使用推荐的本机模型为两个 ≥2B 的模型
（`qwen3.5:2b`、`LiquidAI-dev/lfm2.5-2.6b`）；其他几个我都删掉了后来，只是把被删模型的数据仍保留在此。

> **注意**：思考型模型必须给足 `max_tokens`，否则配额会全花在思考上、可见答案为空。
> 语言测试用 `max_tokens=1200`，工具测试用 `2000`。

## 第一部分 —— 提供商格式兼容性

本部分验证的是承载大多数提供商的那两种线协议：Anthropic Messages 与
OpenAI Chat Completions，两者都做了端到端测试。OpenLaoKe 还原生支持
Google `generateContent`、AWS Bedrock 与 Cohere，这些不在本部分范围内。

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

## 第四部分 —— 具体本地任务

在两个 ≥2B 模型上，用两个外壳、中英双语跑了 5 个具体任务：8 种（外壳, 模型, 语言）组合 × 5 任务 = 40 次。每次运行单独一个目录，位于
`tests/artifacts/pi-small-model-tasks/<外壳>/<模型>/<语言>/<任务>/`，外壳输出在 `run.log`，生成的文件保留原处供人工检查。

| 任务 | 指令（中文） | 通过条件 |
|------|--------------|----------|
| T1 精确写文件 | 在当前目录创建 `hello.txt`，内容正好是 `hello small model` | 文件含该文本 |
| T2 读并求和 | 读 `data.txt`（每行一个整数），求和 | 答案含 `224` |
| T3 写+运行 | 写 `fib.py` 打印前 10 个斐波那契数，并运行 | 脚本可运行并输出 `0 1 1 2 3 5 8 13 21 34` |
| T4 生成产物 | 写 `report.md`，含标题和三条要点 | 有 `#` 标题且 ≥3 条要点 |
| T5 修 bug | 修复 `buggy.py` 中 `average()` 的偏差，并运行 | 去掉 `+ 1`，输出 `4.0` |

`OK` = 通过，`..` = 失败。

| 外壳 | 模型 | 语言 | T1 | T2 | T3 | T4 | T5 | 得分 |
|------|------|------|:--:|:--:|:--:|:--:|:--:|-----:|
| openlaoke | qwen3.5:2b | 中 | OK | OK | OK | .. | OK | 4/5 |
| openlaoke | qwen3.5:2b | 英 | OK | OK | .. | OK | .. | 3/5 |
| openlaoke | LiquidAI-dev/lfm2.5-2.6b | 中 | OK | OK | .. | OK | OK | 4/5 |
| openlaoke | LiquidAI-dev/lfm2.5-2.6b | 英 | OK | .. | .. | OK | OK | 3/5 |
| pi | qwen3.5:2b | 中 | OK | .. | OK | OK | OK | 4/5 |
| pi | qwen3.5:2b | 英 | .. | OK | OK | OK | OK | 4/5 |
| pi | LiquidAI-dev/lfm2.5-2.6b | 中 | OK | OK | .. | OK | OK | 4/5 |
| pi | LiquidAI-dev/lfm2.5-2.6b | 英 | OK | OK | .. | OK | OK | 4/5 |

| 按任务 | 通过 | 按模型 | 通过 | 按外壳 | 通过 | 按语言 | 通过 |
|--------|-----:|--------|-----:|--------|-----:|--------|-----:|
| T1 精确写文件 | 7/8 | qwen3.5:2b | 15/20 | openlaoke | 14/20 | 中 | 16/20 |
| T2 读并求和 | 6/8 | LiquidAI-dev/lfm2.5-2.6b | 15/20 | pi | 16/20 | 英 | 14/20 |
| T3 写+运行 | 3/8 | | | | | | |
| T4 生成产物 | 7/8 | | | | | | |
| T5 修 bug | 7/8 | | | | | | |

### 到底错在哪

失败是模型形态的，不是外壳形态的：

1. **把 `\n` 写成字面量。** 模型在工具参数里放了两个字符 `\` 和 `n`，而不是真的换行。
   LiquidAI-dev 多次如此——`fib.py` 变成单行 `print("Fibonacci test")\n`，报
   `SyntaxError: unexpected character after line continuation character`。
   外壳只是把模型要求的内容原样写入。
2. **定义了却不调用。** `openlaoke + qwen3.5:2b + 英 + T3` 生成了 `fib(n)` 函数却没调用，运行无输出。
3. **复述指令。** `pi + qwen3.5:2b + 中 + T2` 答的是提示词原文，而不是算出的和。

另有一次 600 秒超时（`pi + LiquidAI-dev + 中 + T3`），一次 Python 报错
（`openlaoke + LiquidAI-dev + 中 + T3`）。此处确认的经验法则：写文件基本可靠，读并汇报通常可靠，
而 **写后即运行**（既要通过工具调用产出合法代码、又要真的执行）是小模型翻车的重灾区。

## 第五部分 —— 本地推理速度

通过 Ollama 原生 API 测量，它给出纳秒级的 `prompt_eval_duration` 与 `eval_duration`。
`prefill` = 提示 token 数 / 预填充耗时；`decode` = 生成 token 数 / 解码耗时。
3 次取中位数，输出上限 128 token，Apple M4（10 核 CPU，16 GB 内存），Ollama 0.34.2。

| 模型 | 提示规模 | 提示 token | Prefill (t/s) | Decode (t/s) | 首包 (s) | 总时长 (s) |
|------|----------|-----------:|--------------:|-------------:|---------:|-----------:|
| qwen3.5:2b | 短 | 15 | 142 | 17.2 | 0.11 | 7.72 |
| qwen3.5:2b | 中 | 560 | 5608 | 17.5 | — | 7.41 |
| qwen3.5:2b | 长 | 2210 | 25188 | 17.1 | — | 7.62 |
| LiquidAI-dev/lfm2.5-2.6b | 短 | 17 | 109 | 19.1 | 0.32 | 6.88 |
| LiquidAI-dev/lfm2.5-2.6b | 中 | 560 | 3438 | 18.8 | — | 6.99 |
| LiquidAI-dev/lfm2.5-2.6b | 长 | 2210 | 12675 | 18.8 | — | 7.03 |

“首包”指任何类型的第一个流式分片耗时，两个模型都在 0.35 秒内。对*思考型*模型，更相关的是**首个可见答案**
token 的时间：qwen3.5:2b 把推理放进 `thinking` 字段，思考结束前 `response` 一直为空，所以答案大约在
上表预算（128 token 上限时约 7.5 秒）结束时才出现；LiquidAI-dev 则把 `<think>` 标记直接写进
`response` 流，文字立刻出现（但含思考标记）。

- **Decode** 接近：约 17 t/s（qwen）对约 19 t/s（LiquidAI）。
- **Prefill** 在长上下文下 qwen 更快：2210 token 时约 25k 对约 13k t/s。短提示的 prefill 数字被固定开销主导，只有中/长才有意义。
- **响应感**在短提示下 LiquidAI 更好（无思考延迟），代价是输出里带思考标记。

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

# 4. 具体本地任务（产物写到 tests/artifacts/pi-small-model-tasks）
python scripts/bench_concrete_tasks.py
python scripts/analyze_concrete_tasks.py

# 5. 本地推理速度（prefill / decode / 首包延迟）
python scripts/bench_perf.py
```

以上运行的结果归档在 `bench/results/` 下。

模型列表、提示词与语言分类器的具体实现见 `scripts/` 下对应脚本。
