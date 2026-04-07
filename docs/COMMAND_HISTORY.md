# OpenLaoKe 命令历史功能

## 功能说明

OpenLaoKe 现在支持命令历史记录功能，用户可以使用上下箭头键查看和重用之前输入的命令。

## 使用方法

### 1. 查看历史命令

**按 ↑ 键** - 向上翻阅历史命令（从最新到最旧）

```
OpenLaoKe: /model gpt-4o     # 当前输入
OpenLaoKe: [按 ↑]
OpenLaoKe: /hyperauto task1   # 显示上一条命令
OpenLaoKe: [再按 ↑]
OpenLaoKe: /help              # 显示更早的命令
```

**按 ↓ 键** - 向下翻阅历史命令（从最旧到最新）

```
OpenLaoKe: /help              # 当前显示
OpenLaoKe: [按 ↓]
OpenLaoKe: /hyperauto task1   # 显示下一条命令
```

### 2. 搜索历史命令

**按 Ctrl+R** - 反向搜索历史命令

```
OpenLaoKe: [按 Ctrl+R]
(reverse-i-search)`model': /model gpt-4o  # 输入 "model" 搜索
```

### 3. 重用历史命令

找到历史命令后，按 **Enter** 直接执行，或按 **→** 键编辑后再执行。

## 功能特性

### ✅ 持久化存储

- 历史命令保存在：`~/.openlaoke/command_history.txt`
- 跨会话保持：退出后重新启动，历史记录依然存在
- 自动保存：每次输入的命令自动追加到历史文件

### ✅ 智能搜索

- **前缀匹配**：输入部分命令，按 ↑ 快速定位
- **模糊搜索**：Ctrl+R 支持模糊匹配
- **实时过滤**：输入时自动过滤历史记录

### ✅ 无缝集成

- 与 Tab 自动补全完美配合
- 不影响现有功能
- 零配置开箱即用

## 使用示例

### 示例 1: 快速重用命令

```bash
# 第一次输入
OpenLaoKe: /model ollama/gemma3:27b
✓ Switched to provider: ollama
Model: gemma3:27b

# 稍后想切换回同样的模型
OpenLaoKe: [按 ↑]  # 立即显示上一条命令
OpenLaoKe: /model ollama/gemma3:27b  # 按 Enter 执行
```

### 示例 2: 搜索特定命令

```bash
# 记得之前执行过某个 hyperauto 任务
OpenLaoKe: [按 Ctrl+R]
(reverse-i-search)`hyper': /hyperauto 重构项目
# 按 Enter 执行
```

### 示例 3: 编辑历史命令

```bash
# 找到历史命令
OpenLaoKe: /model ollama/gemma3:1b
# 按 → 键进入编辑模式
OpenLaoKe: /model ollama/gemma3:27b|  # 修改后执行
```

## 历史文件管理

### 文件位置

```
~/.openlaoke/command_history.txt
```

### 文件格式

每行一条命令，按时间顺序记录：

```
/help
/model gpt-4o
/hyperauto 重构项目
/provider ollama
```

### 清理历史

```bash
# 清空历史记录
rm ~/.openlaoke/command_history.txt

# 或在 OpenLaoKe 中
OpenLaoKe: /history clear  # 如果实现了这个命令
```

### 备份历史

```bash
# 备份历史文件
cp ~/.openlaoke/command_history.txt ~/command_history_backup.txt

# 恢复历史
cp ~/command_history_backup.txt ~/.openlaoke/command_history.txt
```

## 快捷键总结

| 快捷键 | 功能 |
|--------|------|
| ↑ | 上一条历史命令 |
| ↓ | 下一条历史命令 |
| Ctrl+R | 反向搜索历史 |
| Ctrl+S | 正向搜索历史 |
| → | 编辑当前历史命令 |
| Ctrl+P | 同 ↑（Emacs风格） |
| Ctrl+N | 同 ↓（Emacs风格） |

## 技术实现

### 依赖库

使用 `prompt_toolkit.history.FileHistory` 实现：

```python
from prompt_toolkit.history import FileHistory

history = FileHistory(str(history_file))

session = PromptSession(
    history=history,
    enable_history_search=True,
)
```

### 特性

- **线程安全**：支持多进程并发写入
- **高效读取**：懒加载，不占用大量内存
- **编码支持**：正确处理 Unicode 字符
- **错误恢复**：文件损坏时自动重建

## 配置选项

### 修改历史文件位置

```python
# 在 openlaoke/core/prompt_input.py 中修改
HISTORY_FILE = Path("/custom/path/history.txt")
```

### 禁用历史记录

```python
# 使用 InMemoryHistory 替代 FileHistory
from prompt_toolkit.history import InMemoryHistory

session = PromptSession(
    history=InMemoryHistory(),  # 仅会话内有效
)
```

## 常见问题

### Q: 历史命令太多怎么办？

A: 历史文件会持续增长，可以定期清理：

```bash
# 只保留最近100条
tail -n 100 ~/.openlaoke/command_history.txt > /tmp/history.txt
mv /tmp/history.txt ~/.openlaoke/command_history.txt
```

### Q: 为什么有些命令没有保存？

A: 只有按 Enter 执行的命令才会保存。Ctrl+C 取消的命令不会记录。

### Q: 可以共享历史记录吗？

A: 可以，将历史文件放在共享目录：

```bash
# 使用符号链接
ln -s /shared/history.txt ~/.openlaoke/command_history.txt
```

### Q: 历史记录会包含密码吗？

A: 所有输入都会保存，包括 API key 等。建议：
- 不要在命令行直接输入敏感信息
- 使用环境变量或配置文件存储密钥

## 最佳实践

### 1. 使用描述性的任务名称

```bash
# 好
/hyperauto 重构authentication模块，使用JWT替代session

# 不好
/hyperauto task1
```

这样历史记录本身就是文档。

### 2. 利用搜索快速定位

```bash
# 输入关键词后立即按 ↑
OpenLaoKe: model [按 ↑]  # 快速找到所有 model 命令
OpenLaoKe: hyper [按 ↑]   # 快速找到所有 hyperauto 命令
```

### 3. 组合使用 Tab 补全

```bash
OpenLaoKe: /model [Tab]   # 查看可选模型
OpenLaoKe: /model gemma [↑]  # 查看历史中的 gemma 相关命令
```

## 版本信息

- **版本**: v0.1.13
- **添加日期**: 2026-04-04
- **实现文件**: `openlaoke/core/prompt_input.py`
- **依赖**: `prompt_toolkit >= 3.0.0`

## 相关功能

- **Tab 自动补全** - `/` 开头的命令自动补全
- **技能快捷方式** - 直接输入技能名称调用
- **多行输入** - 支持 `\` 换行

## 未来改进

### 计划功能

1. **历史命令统计** - 显示最常用的命令
2. **历史标签** - 为重要命令添加标签
3. **历史同步** - 跨设备同步历史记录
4. **智能推荐** - 基于历史推荐命令

### 示例实现

```bash
# 统计最常用命令
/history stats

# 添加标签
/model gpt-4o --tag "work"

# 按标签搜索
/history search --tag work
```

## 用户反馈

### 优点

✅ 不用重复输入长命令  
✅ 快速重用之前的配置  
✅ 搜索功能非常方便  
✅ 与其他 shell 历史习惯一致  

### 改进建议

- 增加历史命令的时间戳
- 支持历史命令的分组显示
- 添加历史命令的删除功能

---

**现在开始使用上下箭头键，享受更高效的命令输入体验！** 🎉
