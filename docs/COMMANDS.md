# OpenLaoKe 命令快速参考

## 核心原则
所有命令都支持**直接参数传递**，无需复杂子命令。

## 输入增强功能

### 命令历史记录
- **↑ / ↓ 键** - 浏览历史命令
- **Ctrl+R** - 搜索历史命令
- **Tab 键** - 自动补全命令和技能名称
- 历史文件位置：`~/.openlaoke/command_history.txt`

**使用示例：**
```bash
OpenLaoKe: /model gemma3:27b
# 稍后按 ↑ 键
OpenLaoKe: /model gemma3:27b  # 自动显示上一条命令

# 搜索包含 "hyper" 的历史命令
OpenLaoKe: [Ctrl+R]
(reverse-i-search)`hyper': /hyperauto 重构项目
```

## 模型与提供商

### `/model` - 模型切换
```bash
/model                          # 显示当前模型和可用列表
/model gpt-4o                   # 按名称切换
/model 1                        # 按序号切换
/model #3                       # 带#前缀的序号
/model ollama/gemma3:27b        # provider/model组合
/model -l                       # 列出所有提供商的所有模型
/model -p                       # 列出所有提供商
```

### `/provider` - 提供商切换
```bash
/provider                       # 显示当前提供商
/provider ollama                # 切换到ollama
/provider anthropic             # 切换到anthropic
```

## HyperAuto 自主模式

### `/hyperauto` - 自主运行
```bash
/hyperauto                      # 显示状态
/hyperauto on                   # 启用
/hyperauto off                  # 禁用
/hyperauto Convert project to C # 直接启动任务（自动启用）
/hyperauto start <task>         # 启动任务
/hyperauto stop                 # 停止任务
/hyperauto progress             # 显示详细进度
/hyperauto resume               # 恢复上次任务
/hyperauto config               # 显示配置
/hyperauto config max_iterations=200  # 修改配置
/hyperauto history              # 显示历史
/hyperauto learn                # 切换学习模式
```

**别名：** `/ha`, `/auto`, `/hyper`

**示例：**
```bash
OpenLaoKe: /hyperauto 将当前项目翻译成纯C语言版本

✓ HyperAuto Started
  Task ID: ha_20260404_190159
  Mode: semi_auto
  Task: 将当前项目翻译成纯C语言版本
  Timeout: 300s

OpenLaoKe: /hyperauto progress

HyperAuto Task Progress

  Task ID:  ha_20260404_190159
  Status:   running
  Duration: 2m 15s

  Task: 将当前项目翻译成纯C语言版本

  Progress: [███████████░░░░░░░░░░░░░░░░░] 35.0%
  Iterations: 35/100

  Steps:
    ✓ 1. Analyze project structure
    ✓ 2. Generate C header files
    ● 3. Convert Python to C
    ○ 4. Create build system
    ○ 5. Test compilation

  Recent Actions:
    • Created main.c with basic structure
    • Converted utils.py to utils.c
    • Working on type conversions
```

## 配置管理

### `/permission` - 权限模式
```bash
/permission                     # 显示当前模式
/permission auto                # 切换到自动模式
/permission default             # 切换到默认模式
/permission bypass              # 切换到绕过模式
```

### `/theme` - 主题切换
```bash
/theme                          # 显示当前主题
/theme dark                     # 切换到暗色主题
/theme light                    # 切换到亮色主题
```

### `/vim` - Vim模式
```bash
/vim                            # 显示Vim模式状态
/vim on                         # 启用Vim模式
/vim off                        # 禁用Vim模式
/vim toggle                     # 切换Vim模式
```

## 技能管理

### `/skill` - 技能管理
```bash
/skill                          # 列出所有技能
/skill list                     # 列出所有技能
/skill install <url>            # 从GitHub安装技能
/skill remove <name>            # 删除技能
/skill info <name>              # 显示技能详情
/skill humanizer                # 显示技能详情（简写）
```

### `/use` - 激活技能
```bash
/use humanizer                  # 激活humanizer技能
/use academic-writer            # 激活学术写作技能
```

**快捷方式：** 直接使用 `/<skill_name>`
```bash
/humanizer AI生成的文本...      # 直接使用技能
/academic-writer 写一篇论文...   # 直接使用技能
```

## 内存管理

### `/memory` - 持久化内存
```bash
/memory                         # 列出所有记忆
/memory add 重要信息：项目使用Python 3.11  # 添加记忆
/memory remove 1                # 删除第1条记忆
/memory clear                   # 清空所有记忆
```

## 工作目录

### `/cwd` - 工作目录
```bash
/cwd                            # 显示当前工作目录
/cwd /path/to/project           # 切换工作目录
```

## MCP服务器

### `/mcp` - MCP管理
```bash
/mcp                            # 列出所有MCP服务器
/mcp list                       # 列出所有MCP服务器
/mcp enable <name>              # 启用服务器
/mcp disable <name>             # 禁用服务器
```

## 其他命令

### 会话管理
```bash
/help                           # 显示帮助
/clear                          # 清屏
/exit                           # 退出
/quit                           # 退出（别名）
/resume                         # 恢复上次会话
/compact                        # 压缩对话
```

### 信息查询
```bash
/cost                           # 显示费用和token使用量
/usage                          # 显示详细使用统计
/settings                       # 显示当前设置
/doctor                         # 诊断配置问题
/commands                       # 显示示例命令
/history                        # 显示命令历史
```

### 开发工具
```bash
/hooks                          # 管理钩子
/hooks list                     # 列出钩子
/hooks test <type>              # 测试钩子
/agents                         # 显示可用代理类型
/export                         # 导出会话
/undo                           # 撤销上次操作
/init                           # 初始化项目配置
```

## 使用技巧

### 1. Tab补全
- 技能名称支持Tab补全
- 文件路径支持Tab补全
- 命令名称支持Tab补全

### 2. 简写形式
大多数命令都有简写：
- `/model` → `/m`
- `/provider` → `/p`
- `/hyperauto` → `/ha` 或 `/auto`
- `/skill` → `/skills`
- `/exit` → `/quit` 或 `/q`

### 3. 直接参数传递
无需记住复杂子命令：
```bash
# 传统方式
/model
> Current model: gemma3:1b
> Available models:
>   [1] gpt-4o
>   [2] gemma3:27b
/model 2

# 简洁方式
/model gemma3:27b
```

### 4. 自动启用功能
某些命令会自动启用：
```bash
/hyperauto <task>  # 如果未启用，会自动启用HyperAuto
```

## 完整示例

### 场景1：切换模型并开始工作
```bash
OpenLaoKe: /model
Current provider: ollama
Current model: gemma3:1b

Available models (ollama):
  [1] gemma4:e2b
  [2] gemma3:27b
  [3] gemma3:1b (current)

OpenLaoKe: /model 2
✓ Model set to: gemma3:27b

OpenLaoKe: 写一个快速排序算法
```

### 场景2：使用HyperAuto自动完成任务
```bash
OpenLaoKe: /hyperauto 重构authentication模块，使用JWT替代session

✓ HyperAuto Started
  Task ID: ha_20260404_190200
  Task: 重构authentication模块，使用JWT替代session
  Mode: semi_auto

[AI开始自主工作...]
```

### 场景3：使用技能
```bash
OpenLaoKe: /academic-writer 写一篇关于LLM效率优化的论文

[学术写作技能已激活]
[自动下载参考文献...]
✓ Downloaded: attention-is-all-you-need.pdf
✓ Downloaded: llama-2-open-foundation.pdf

[开始撰写论文...]
```

### 场景4：记忆重要信息
```bash
OpenLaoKe: /memory add 项目使用FastAPI框架，数据库是PostgreSQL

✓ Memory added: 项目使用FastAPI框架，数据库是PostgreSQL

OpenLaoKe: /memory
Memory Storage:
  [1] 项目使用FastAPI框架，数据库是PostgreSQL (2026-04-04T19:02:00)
```

## 经验教训与自我反思

### `/lessons` - 查看经验教训和策略统计
```bash
/lessons                          # 完整经验教训报告
/lessons done                     # 显示已实现的改进
/lessons pending                  # 显示待实现的改进
/lessons stats                    # 显示策略统计数据
/lessons summary                  # 显示自我反思追踪摘要
```

**工作原理：**
- 系统自动记录每个策略的成功/失败结果
- 按模型尺寸计算成功率
- 自动禁用成功率<30%的策略（10次尝试后）
- 生成基于数据的推荐
- 数据持久化在 `~/.openlaoke/lessons/lessons.json`

## 键盘快捷键

- `Tab` - 自动补全
- `Ctrl+C` - 中断当前操作
- `Ctrl+D` - 退出
- `Ctrl+L` - 清屏
- `↑` / `↓` - 历史命令导航

## 获取帮助

```bash
/help                           # 通用帮助
/help <command>                 # 特定命令帮助
/<command> (无参数)             # 显示命令用法
```

## 配置持久化

所有配置更改会自动保存到 `~/.openlaoke/config.json`：
- 模型选择
- 提供商配置
- HyperAuto设置
- 主题偏好
- 内存数据

会话文件保存在 `~/.openlaoke/sessions/`。