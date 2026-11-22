# 本地小模型的四 Harness 横评

测试日期：2026-11-22。同一台 Apple Silicon M4，同一个本地模型，同一段提示词，
分别交给 OpenLaoKe、pi、Jcode、OpenCode 执行。结果只认文件系统：脚本在全新目录
里运行，结束后单独执行模型生成的 Python 文件，输出匹配才算通过；模型自己说
“完成了”不算。

脚本：`bench/harness_matrix.py`。原始结果：`bench/results/*.json`。

## 设置

- 模型：LFM3-1.7B（GGUF Q8_0，llama.cpp 1.0.0）、Qwen3.5-2B（MLX 4bit，
  mlx-lm server）。
- 任务：
  - `fib`：创建 `answer.py`，迭代 Fibonacci，打印 `fib(10)`，期望 `55`。
  - `merge`：创建 `merge_sort.py`，归并排序，打印排序后的 `[1, 2, 3, 4, 5]`。
- 每个 harness 在独立临时目录中运行；不共享会话、不共享缓存。
- 脚本显式设置子进程的 `PWD`，否则 OpenCode 会跟随父 shell 的 `PWD`，把文件
  写回仓库而不是临时目录，验证就会误判成“没有文件”。
- 超时：LFM3 每项 150 秒，Qwen 每项 200 秒。
- OpenLaoKe 使用 `--max-steps 25`；四个 harness 都关闭权限确认。
- thinking 对本地模型主要是服务端开关：
  - llama.cpp：`--reasoning on|off`
  - MLX：`--chat-template-args '{"enable_thinking": true|false}'`
- 速度同时记录两个时间：
  - `artifact`：目标文件第一次出现的时间。
  - `exit`：harness 进程退出的时间。
  两者差距大，说明任务其实做完了，但 agent 循环没有停。

## LFM3-1.7B GGUF：thinking off

| Harness | fib 结果 | fib artifact | fib exit | merge 结果 | merge artifact | merge exit |
|---|---|---:|---:|---|---:|---:|
| OpenLaoKe | 文件正确，超时 | 21.8s | 150s | **通过** | 22.3s | 47.5s |
| pi | **通过** | 62.4s | 71.3s | 无文件，自称完成 | - | 73.3s |
| Jcode | **通过** | 45.3s | 61.6s | **通过** | 7.8s | 28.0s |
| OpenCode | 无文件，超时 | - | 150s | 无文件，超时 | - | 150s |

总计 4/8。

## LFM3-1.7B GGUF：thinking on

| Harness | fib 结果 | fib artifact | fib exit | merge 结果 | merge artifact | merge exit |
|---|---|---:|---:|---|---:|---:|
| OpenLaoKe | **通过** | 32.3s | 102.3s | 文件正确，超时 | 45.6s | 150s |
| pi | **通过** | 59.9s | 96.8s | **通过** | 113.4s | 129.1s |
| Jcode | **通过** | 73.6s | 99.4s | **通过** | 42.1s | 73.8s |
| OpenCode | 无文件，超时 | - | 150s | 无文件，超时 | - | 150s |

总计 5/8。

## Qwen3.5-2B MLX：thinking off / on

只跑 `fib` 任务。

| Harness | off 结果 | off artifact | off exit | on 结果 | on artifact | on exit |
|---|---|---:|---:|---|---:|---:|
| OpenLaoKe | **通过** | 23.6s | 75.1s | **通过** | 25.8s | 126.7s |
| pi | 无文件，自称完成 | - | 49.1s | **通过** | 57.8s | 62.9s |
| Jcode | 文件错误（34），超时 | 44.6s | 200s | **通过** | 49.8s | 66.9s |
| OpenCode | 文件错误（34），exit 1 | 118.9s | 131.9s | 无文件，超时 | - | 200s |

off 1/4，on 3/4。Qwen 与 LFM3 相反：**thinking 打开后质量明显变好**，
Jcode 从“文件算错且循环”变成 66.9 秒通过。

## 观察

1. **Jcode 在这组测试里最稳。** LFM3 两项、两种 thinking 都是 4/4，而且
   artifact 时间通常最短（merge off 只用 7.8 秒）。
2. **OpenLaoKe 生成文件最快，但常常不退出。** LFM3 off 的 fib 在 21.8 秒就写出
   正确文件，却一直跑到 150 秒超时；Qwen on 的 fib 也是 25.8 秒出文件、126.7 秒
   才退出。问题不在生成，而在“任务完成后如何停”。
3. **pi 有一次假成功。** LFM3 off 的 merge，pi 退出码 0、回复“已验证”，但目录
   里没有 `merge_sort.py`。只看退出码会把它算成通过。
4. **OpenCode 在这两个小模型上 0/8。** 它给本地模型的任务提示和工具 schema
   太重：Qwen 的一次请求预填充达到 29,025 token，2B 模型很难在预算内完成；
   Qwen 关闭 thinking 时虽然写出了文件，但 Fibonacci 起点错一位，输出 34，
   随后工具参数又不符合 schema，最终 exit 1。
5. **thinking 不是免费开关。** LFM3 打开后，多数通过项慢 30%-120%；Qwen 打开后
   反而因为少走弯路而变快（Jcode 200s 超时 -> 66.9s 通过）。是否打开取决于模型，
   不能一刀切。
6. **超时要分两种。** “文件正确但没退出”和“根本没做出来”是两件事。表里把
   `artifact` 和 `exit` 分开，就是为了不把前者误判成模型能力问题。

## 复现

```bash
# 先按 docs/lfm3-local-models.md 启动对应服务，并设置好四个 harness 的 provider
python bench/harness_matrix.py --model lfm3-gguf --thinking off --task all \
  --timeout 150 --json bench/results/lfm3-gguf-thinking-off-all.json
python bench/harness_matrix.py --model lfm3-gguf --thinking on --task all \
  --timeout 150 --json bench/results/lfm3-gguf-thinking-on-all.json
python bench/harness_matrix.py --model qwen-mlx --thinking off --task fib \
  --timeout 200 --json bench/results/qwen-mlx-thinking-off-fib.json
python bench/harness_matrix.py --model qwen-mlx --thinking on --task fib \
  --timeout 200 --json bench/results/qwen-mlx-thinking-on-fib.json
```

服务端 thinking 开关：

```bash
# llama.cpp
llama-server -m LFM3-1.7B-Q8_0.gguf --alias lfm3-1.7b --port 8080 \
  --reasoning off --jinja --no-webui

# MLX，Qwen
mlx_lm.server --model qwen3.5-2b-mlx4 --port 8084 \
  --chat-template-args '{"enable_thinking": true}'
```

注意：`mlx_lm.server` 的 `/v1/models` 返回的是模型绝对路径，请求里的 `model`
必须与它完全一致；否则服务端会去 HuggingFace 找模型，表现为长时间无响应。
