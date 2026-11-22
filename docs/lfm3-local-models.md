# LFM3 本地模型对比

测试日期：2026-11-22。机器：Apple Silicon（M4），macOS。四个模型都通过
OpenAI 兼容接口测试，速度取 3 次、每次生成 220 token 的中位数。

## 结论

| 模型 | 运行时 | 量化 | 权重 | 生成速度 | 预填充速度 | 6 项文本测试 | 图像 | 建议 |
|---|---|---|---:|---:|---:|---:|---|---|
| LFM3-1.7B GGUF | llama.cpp 1.0.0 | Q8_0 | 1.7 GB | 19.6 tok/s | 165 tok/s | 6/6 | - | 便携备选，必须 `--reasoning off` |
| **LFM3-1.7B MLX** | MLX-VLM 0.8.0 | 8bit | 1.84 GB | **25.5 tok/s** | **395 tok/s** | **6/6** | - | **纯文本编码首选** |
| LFM3-Omni-2B GGUF | llama.cpp 1.0.0 | Q8_0 + mmproj | 1.85 + 0.51 GB | 21.4 tok/s | 177 tok/s | 6/7 | 通过 | 需要多模态时的便携备选 |
| **LFM3-Omni-2B MLX** | MLX-VLM 0.8.0 | 8bit | 2.71 + 0.15 GB | **25.1 tok/s** | **427 tok/s** | 6/7 | 通过 | **需要图像/音频时首选** |

一句话：**纯写代码选 LFM3-1.7B-MLX-8bit；需要图片/音频选
LFM3-Omni-2B-MLX-8bit。** MLX 比 llama.cpp 生成快约 18-30%，长提示词预填充快约
2.3 倍。

和当初的 Qwen3.5-2B 比：**LFM3-1.7B MLX 8bit 与 Qwen3.5-2B MLX 4bit 同为
6/6，LFM3 慢约 15% 但权重更小、量化更高；GGUF 侧 LFM3-1.7B Q8 比 Qwen Q4
更快也更准。** Qwen3.5-2B MLX 4bit 仍是这次绝对速度最快的，但必须关掉
thinking。

## 与 Qwen3.5-2B 对比

同一套 6 项文本测试、同一台机器。速度是生成 220 token 的端到端墙钟速度
（包含预填充），不是只算 decode。

| 模型 | 量化 | 端到端速度 | 文本质量 | Agent 任务 |
|---|---|---:|---:|---|
| LFM3-1.7B GGUF | Q8_0 | 19.3 tok/s | 6/6 | 文件正确，循环未退出 |
| **LFM3-1.7B MLX** | 8bit | 24.7 tok/s | **6/6** | 文件正确，循环未退出 |
| LFM3-Omni-2B GGUF | Q8_0 | 21.1 tok/s | 6/7 | 文件正确，循环未退出 |
| LFM3-Omni-2B MLX | 8bit | 24.3 tok/s | 6/7 | 文件正确，循环未退出 |
| Qwen3.5-2B GGUF | Q4_K_M | 16.2 tok/s | 5/6 | 文件正确，循环未退出 |
| Qwen3.5-2B MLX | 4bit | **28.5 tok/s** | 6/6 | 文件正确，循环未退出 |

解读：

- **Qwen3.5-2B MLX 4bit 是这次最快的**，28.5 tok/s，文本 6/6。它比
  LFM3-1.7B MLX 8bit 快约 15%，但用的是 4bit，模型也大一点（2B vs 1.7B）。
- **LFM3-1.7B 的 8bit 版本质量和 Qwen 4bit 打平（都是 6/6）**，速度只慢 15%，
  权重更小。综合更稳。
- **LFM3-1.7B GGUF Q8 全面胜过 Qwen3.5-2B GGUF Q4**：19.3 vs 16.2 tok/s，
  6/6 vs 5/6。Qwen GGUF 的找零题答成 17，LFM3 答对 27。
- **Qwen3.5-2B MLX 必须关闭 thinking**：`mlx_lm.server` 默认会让它把 token
  全花在 `reasoning` 上，`content` 为空；第一次测只有 2/6。启动时加
  `--chat-template-args '{"enable_thinking":false}'` 后恢复到 6/6。这和 LFM3
  GGUF 必须加 `--reasoning off` 是同一类问题。
- **Agent 任务六个模型都没自行结束**：都正确创建了 `hello.py` 并输出 42，但
  120-150 秒内循环不退出。此前 Qwen3.5-2B MLX 在 5 个文档任务上是 0/5、平均
  125.5 秒；LFM3 还没跑那套文档任务。结论不变：这些小模型适合直接生成/解释，
  不适合长时间无人值守的 agent。

## 测试内容

文本测试共 6 项，全部有可执行或可解析的判据：

1. `fib-code`：生成迭代 Fibonacci，执行后必须输出 `55`。
2. `code-fix`：修复 `return a - b`，执行 `add(2, 3)` 必须输出 `5`。
3. `json`：只输出指定 JSON，解析后字段必须完全匹配。
4. `tool-call`：给出 `write_file` 工具，必须返回正确的函数名和
   `{"path":"hello.txt","content":"hi"}`。
5. `reasoning`：四支笔、三本笔记本、50 元找零，答案必须是 `27`。
6. `instruction`：只回复 `PONG`。

Omni 额外测试一张纯红 PNG，回答必须包含 `red`。

## 结果细节

### 文本质量

- LFM3-1.7B：GGUF 和 MLX 都是 **6/6**。代码生成、修 bug、JSON、工具调用、
  算术、严格指令都通过。
- LFM3-Omni-2B：GGUF 和 MLX 都是 **6/7**。代码、JSON、工具调用、图像都通过，
  但找零题都只回 `5`，算术能力明显弱于 1.7B。这是模型能力差异，不是运行时差异。

### 速度

- 1.7B MLX 比 GGUF：生成 +30%，预填充 +139%。
- Omni MLX 比 GGUF：生成 +18%，预填充 +141%。
- 速度测试的 220 token 生成耗时：MLX 8.9-9.1 秒，GGUF 10.4-11.4 秒。

### Agent 任务

用 OpenLaoKe `--local` 让四个模型各做一次：

> Create hello.py that prints 42. Run it to verify.

四个模型都正确创建了 `hello.py`，单独执行都输出 `42`。但在 150 秒内都没有
自行结束，agent 循环一直在继续。此前 1.7B MLX 做 Fibonacci 任务时曾在 77 秒内
正常结束，所以不是完全不能用，而是 1.7B/2B 模型与当前的“执行-验证”循环配合
不稳定。结论：**它们适合当直接代码模型，暂时不适合长时间无人值守的 agent。**
后续应给本地小模型降低最大步数，或增加“任务已完成”的早停判据。

后续补充：`docs/harness-matrix.md` 把 LFM3-1.7B 和 Qwen3.5-2B 分别接到
OpenLaoKe、pi、Jcode、OpenCode，分 thinking 开/关跑了 `fib` 与 `merge`
两个任务。修复“本地脚本验证被拦”和“验证后不终止”之后，OpenLaoKe 6/6 全通过，
并且在 6 个场景里 5 个最快；Jcode 5/6；pi 出现过“自称完成但没有文件”；
OpenCode 在 1.7B/2B 上 0/8。

## 关键坑

1. **llama.cpp 跑 LFM3-1.7B 必须加 `--reasoning off`。** 否则模型会把 token
   预算花在思考上，`content` 可能为空，第一次测试只有 2/6。Omni 的 llama.cpp
   启动也建议加 `--reasoning off`。
2. **MLX 版本要用 MLX-VLM，不是 mlx-lm。** LFM3 的架构是 `Lfm3ForCausalLM`，
   `mlx-lm 0.31.3` 没有 `lfm3` 模块；官方 MLX 仓库要求 `mlx-vlm>=0.7.11`，
   启动时加 `--trust-remote-code`。
3. **MLX-VLM 会返回 `tool_calls: null`。** OpenLaoKe 已修复，解析时把 `null`
   当作空列表，不会再报 `'NoneType' object is not iterable`。
4. **Omni 是多模态模型，权重更大。** 1.7B MLX 8bit 约 1.84 GB；Omni MLX 8bit
   约 2.88 GB（含音频 codec）。如果只做文本编码，1.7B 更划算。

## 复现

启动 MLX：

```bash
mlx_vlm.server --model ~/models/LFM3-1.7B-MLX-8bit --host 127.0.0.1 --port 8081 --trust-remote-code
mlx_vlm.server --model ~/models/LFM3-Omni-2B-MLX-8bit --host 127.0.0.1 --port 8082 --trust-remote-code
```

启动 llama.cpp：

```bash
llama-server -m ~/models/LFM3-1.7B-GGUF/LFM3-1.7B-Q8_0.gguf \
  --alias lfm3-1.7b --port 8080 --reasoning off --jinja --no-webui

llama-server -m ~/models/LFM3-Omni-2B-GGUF/LFM3-Omni-2B-Q8_0.gguf \
  --mmproj ~/models/LFM3-Omni-2B-GGUF/mmproj-LFM3-Omni-2B-Q8_0.gguf \
  --alias lfm3-omni-2b --port 8083 --reasoning off --jinja --no-webui
```

OpenLaoKe 已配置四个 provider：`lfm3_1_7b_gguf`、`lfm3_mlx`、
`lfm3_omni_gguf`、`lfm3_omni_mlx`。跑完整对比：

```bash
python bench/lfm3_compare.py --agent
```
