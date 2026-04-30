# OpenLaoKe 安装手册

> 详细安装指南，涵盖所有平台、所有安装方式和常见问题排查。

## 目录

1. [系统要求](#系统要求)
2. [快速安装](#快速安装)
3. [详细安装步骤](#详细安装步骤)
4. [本地GGUF模型安装](#本地gguf模型安装)
5. [配置指南](#配置指南)
6. [首次运行](#首次运行)
7. [运行模式](#运行模式)
8. [常见问题排查](#常见问题排查)
9. [卸载](#卸载)

---

## 系统要求

### 基本要求
- **Python**: 3.11 或更高版本
- **操作系统**: macOS、Linux、Windows
- **内存**: 最低 512 MB（本地模型需 1 GB+）
- **磁盘**: 最低 100 MB（不含模型文件）

### 本地GGUF模型额外要求
- **内存**: 
  - Qwen2.5 0.5B: 512 MB+
  - Qwen3 0.6B: 1 GB+
  - Qwen2.5 1.5B: 2 GB+
  - Qwen2.5 3B: 4 GB+
- **CPU**: 支持AVX2指令集（现代CPU均支持）
- **磁盘**: 每个模型 469 MB - 1.9 GB

### 推荐配置
- **Python**: 3.12
- **内存**: 8 GB+
- **CPU**: Apple Silicon (M1/M2/M3) 或现代x86_64
- **网络**: 稳定网络连接（云端提供商）

---

## 快速安装

### 使用 pip（推荐）
```bash
# 直接从 PyPI 安装
pip install openlaoke

# 或从源码安装
git clone https://github.com/cycleuser/OpenLaoKe.git
cd OpenLaoKe
pip install -e .

# 开发版本（含测试工具）
pip install -e ".[dev]"
```

### 使用 uv（更快）
```bash
# 安装uv（如果还没有）
pip install uv

# 克隆并安装
git clone https://github.com/cycleuser/OpenLaoKe.git
cd OpenLaoKe
uv pip install -e ".[dev]"
```

### 验证安装
```bash
openlaoke --help
```

---

## 详细安装步骤

### 步骤 1: 检查Python版本

```bash
python --version
# 或
python3 --version
```

确保版本 ≥ 3.11。如果版本过低，请升级Python：

**macOS:**
```bash
# 使用Homebrew
brew install python@3.12
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev
```

**Windows:**
从 [python.org](https://www.python.org/downloads/) 下载最新安装程序。

### 步骤 2: 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 验证
python --version
```

### 步骤 3: 安装OpenLaoKe

```bash
# 进入项目目录
cd OpenLaoKe

# 基础安装（含所有功能，包括本地模型支持）
pip install -e .

# 开发安装（含测试和lint工具）
pip install -e ".[dev]"
```

### 步骤 4: 验证安装

```bash
# 检查命令可用
openlaoke --help

# 检查版本
openlaoke --version

# 运行诊断
openlaoke doctor
```

---

## 本地GGUF模型安装

### 方式一：安装时已包含本地支持

`pip install openlaoke` 已包含 `llama-cpp-python`，无需额外安装。

如果编译失败，可手动安装：

```bash
# 基础安装
pip install llama-cpp-python

# 带Metal支持（macOS Apple Silicon）
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python

# 带CUDA支持（NVIDIA GPU）
CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python

# 带Vulkan支持（AMD/Intel GPU）
CMAKE_ARGS="-DLLAMA_VULKAN=on" pip install llama-cpp-python
```

### 验证本地模型支持

```bash
python -c "from llama_cpp import Llama; print('llama-cpp-python OK')"
```

### 下载内置模型

```bash
# 下载Qwen3 0.6B（推荐入门）
openlaoke model download qwen3:0.6b

# 下载Qwen2.5 0.5B（最小资源）
openlaoke model download qwen2.5:0.5b

# 列出所有可用模型
openlaoke model list
```

### 搜索和下载自定义模型

```bash
# 搜索ModelScope上的GGUF模型
openlaoke model search qwen3.5

# 下载指定ModelScope模型
openlaoke model download "unsloth/Qwen3.5-0.8B-GGUF"

# 下载时会列出所有量化版本供选择
# 推荐选择 Q4_K_M 或 Q5_K_M（质量和大小平衡）
```

### 模型存储位置

- 模型文件：`~/.openlaoke/models/`
- 模型注册表：`~/.openlaoke/models/custom_models.json`
- 日志文件：`~/.openlaoke/logs/`

---

## 配置指南

### 首次配置向导

首次运行 `openlaoke` 会自动启动配置向导：

```bash
openlaoke
```

向导会引导你：
1. 选择AI提供商（24个选项）
2. 输入API密钥（如需要）
3. 选择模型
4. 配置代理（可选）

### 重新配置

```bash
openlaoke --config
```

### 配置文件位置

```
~/.openlaoke/
├── config.json              # 主配置文件
├── sessions/                # 会话文件
├── models/                  # 本地GGUF模型
│   ├── custom_models.json   # 自定义模型注册表
│   └── *.gguf               # 模型文件
└── logs/                    # 日志文件
```

### 手动编辑配置

```bash
# 编辑配置文件
nano ~/.openlaoke/config.json
```

示例配置（本地模型）：
```json
{
  "providers": {
    "active_provider": "local_builtin",
    "active_model": "qwen3:0.6b",
    "local_n_ctx": 262144,
    "local_temperature": 0.3,
    "local_repetition_penalty": 1.1,
    "providers": {
      "local_builtin": {
        "default_model": "qwen3:0.6b",
        "enabled": true
      }
    }
  },
  "proxy_mode": "none",
  "max_tokens": 8192,
  "temperature": 1.0,
  "theme": "dark"
}
```

### 环境变量配置

也可以通过环境变量配置API密钥：

```bash
# 设置API密钥
export ANTHROPIC_API_KEY="your-key-here"
export OPENAI_API_KEY="your-key-here"

# 设置默认模型
export OPENLAOKE_MODEL="gpt-4o"

# 设置代理
export HTTP_PROXY="http://127.0.0.1:7890"
export HTTPS_PROXY="http://127.0.0.1:7890"
```

---

## 首次运行

### 基本使用

```bash
# 启动交互式模式
openlaoke

# 启动后直接对话
OpenLaoKe: 你好，请帮我写一个Python排序函数
```

### 常用命令

```
/help          - 显示所有命令
/model         - 查看/切换模型
/provider      - 查看/切换提供商
/settings      - 查看当前设置
/clear         - 清屏和对话
/exit          - 退出
```

### 模型切换

```
# 在REPL中
/model gpt-4o
/model ollama/llama3.2
/model #3              # 按序号选择

# 或使用Ctrl+P弹出选择器
```

---

## 运行模式

### 1. 交互式REPL（默认）

```bash
openlaoke
```

完整的交互式终端界面，支持所有功能。

### 2. 非交互模式

```bash
openlaoke "帮我写一个快速排序算法"
```

单次执行，适合脚本调用。

### 3. 本地模式

```bash
openlaoke --local
```

启用原子任务分解和监督，适合小型本地模型。

### 4. Web UI

```bash
# 默认（localhost:8080）
openlaoke web

# 指定端口
openlaoke web --port 9000

# 局域网访问
openlaoke web --host 0.0.0.0 --port 8080
```

### 5. API Server

```bash
openlaoke server
```

启动FastAPI后端，默认 localhost:3000。

---

## 常见问题排查

### 问题1: `openlaoke: command not found`

**原因**: 安装路径不在PATH中

**解决方案**:
```bash
# 检查安装位置
pip show openlaoke

# 添加Python bin目录到PATH
export PATH="$HOME/.local/bin:$PATH"

# 或使用完整路径
python -m openlaoke.entrypoints.cli
```

### 问题2: `llama-cpp-python` 编译失败

**原因**: 缺少编译工具或依赖

**macOS解决方案**:
```bash
# 安装Xcode命令行工具
xcode-select --install

# 重试安装
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python
```

**Linux解决方案**:
```bash
# 安装编译工具
sudo apt install build-essential cmake

# 重试安装
pip install llama-cpp-python
```

**Windows解决方案**:
```bash
# 安装Visual Studio Build Tools
# 从 https://visualstudio.microsoft.com/visual-cpp-build-tools/ 下载

# 或使用预编译wheel
pip install llama-cpp-python --only-binary :all:
```

### 问题3: 模型下载失败

**原因**: 网络问题或ModelScope访问问题

**解决方案**:
```bash
# 检查网络连接
ping www.modelscope.cn

# 使用代理
openlaoke --proxy http://127.0.0.1:7890 model download qwen3:0.6b

# 手动下载模型文件到 ~/.openlaoke/models/
# 然后创建 custom_models.json 注册
```

### 问题4: 模型加载后内存不足

**原因**: 模型大小超过可用内存

**解决方案**:
```bash
# 使用更小的模型
openlaoke model download qwen2.5:0.5b  # 469 MB

# 或减小上下文窗口
/localconfig n_ctx 8192
```

### 问题5: 模型输出重复内容

**原因**: 温度过低或重复惩罚不足

**解决方案**:
```bash
# 在REPL中调整
/localconfig temperature 0.5
/localconfig repetition_penalty 1.2
```

### 问题6: API密钥无效

**原因**: 密钥错误或过期

**解决方案**:
```bash
# 重新配置
openlaoke --config

# 或直接编辑配置
nano ~/.openlaoke/config.json

# 检查环境变量
echo $ANTHROPIC_API_KEY
echo $OPENAI_API_KEY
```

### 问题7: Web UI无法访问

**原因**: 端口占用或防火墙

**解决方案**:
```bash
# 检查端口占用
lsof -i :8080

# 使用其他端口
openlaoke web --port 9000

# 检查防火墙
sudo ufw status  # Linux
```

### 问题8: 中文输出乱码

**原因**: 终端编码问题

**解决方案**:
```bash
# 设置UTF-8
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

# macOS Terminal中
# 偏好设置 -> 描述文件 -> 高级 -> 字符编码 -> UTF-8
```

### 问题9: 技能加载失败

**原因**: 技能文件路径或格式问题

**解决方案**:
```bash
# 检查技能目录
ls ~/.config/opencode/skills/

# 查看技能列表
/skill --list

# 重新加载技能
# 重启OpenLaoKe即可
```

### 问题10: 会话无法恢复

**原因**: 会话文件损坏

**解决方案**:
```bash
# 查看会话文件
ls ~/.openlaoke/sessions/

# 删除损坏的会话
rm ~/.openlaoke/sessions/*.json

# 重新启动
openlaoke
```

---

## 卸载

### 完全卸载

```bash
# 卸载包
pip uninstall openlaoke

# 删除配置和数据
rm -rf ~/.openlaoke/

# 删除技能（如果需要）
rm -rf ~/.config/opencode/skills/
```

### 保留配置卸载

```bash
# 仅卸载包，保留配置
pip uninstall openlaoke
```

---

## 获取帮助

- **GitHub Issues**: https://github.com/cycleuser/OpenLaoKe/issues
- **文档**: README.md, README_CN.md
- **命令帮助**: `openlaoke --help`
- **诊断工具**: `openlaoke doctor`
