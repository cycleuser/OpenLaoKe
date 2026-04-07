# HyperAuto 参数错误修复

## 问题
用户报告错误：
```
✗ HyperAuto Error: HyperAutoConfig.__init__() got an unexpected keyword argument 'timeout_seconds'
```

## 根本原因
在 `openlaoke/commands/hyperauto_command.py` 第 719 行：
```python
# 错误代码
ha_config = HAutoConfig(
    timeout_seconds=hyperauto_config.timeout_seconds,  # ❌ 错误参数名
)
```

`HyperAutoConfig` 的正确参数是 `timeout_per_task`，而不是 `timeout_seconds`。

## 修复方案

### 文件：`openlaoke/commands/hyperauto_command.py`

**修改前（第 719 行）：**
```python
timeout_seconds=hyperauto_config.timeout_seconds,
```

**修改后：**
```python
timeout_per_task=hyperauto_config.timeout_seconds,
```

## HyperAutoConfig 正确参数列表

根据 `openlaoke/core/hyperauto/config.py`：

```python
class HyperAutoConfig:
    mode: HyperAutoMode = HyperAutoMode.FULL_AUTO
    max_iterations: int = 100
    auto_create_skills: bool = True
    auto_init_projects: bool = True
    auto_search_code: bool = True
    auto_install_deps: bool = True
    auto_run_tests: bool = True
    auto_commit: bool = False
    confidence_threshold: float = 0.8
    reflection_enabled: bool = True
    learning_enabled: bool = True
    max_parallel_tasks: int = 5
    timeout_per_task: float = 300.0        # ✅ 正确的参数名
    rollback_on_failure: bool = True
    dry_run: bool = False
    verbose: bool = False
```

## 测试验证

### 1. 配置创建测试
```python
config = HAutoConfig(
    mode="semi_auto",
    max_iterations=50,
    timeout_per_task=300,      # ✅ 正确
    learning_enabled=True,
    reflection_enabled=True,
)
# ✓ 创建成功
```

### 2. Agent 创建测试
```python
agent = HyperAutoAgent(app_state, config)
# ✓ 创建成功
```

### 3. 实际执行测试
```python
# 启动任务
/hyperauto 测试任务
# ✓ 任务启动成功
# ✓ 任务状态: running
# ✓ 任务文件创建成功

# 查看进度
/hyperauto progress
# ✓ 包含进度条
# ✓ 包含步骤列表

# 停止任务
/hyperauto stop
# ✓ 任务停止成功
```

## 完整测试结果

```
=== 全面测试 HyperAuto 功能 ===

1. 模块导入测试:
   ✓ HAutoConfig 导入成功

2. 配置创建测试:
   ✓ HAutoConfig 创建成功
     - mode: semi_auto
     - max_iterations: 50
     - timeout_per_task: 300

3. HyperAutoCommand 方法测试:
   ✓ _execute_hyperauto_task: True
   ✓ _start_hyperauto: True
   ✓ _show_progress: True
   ✓ _start_with_task: True

4. HyperAutoAgent 创建测试:
   ✓ HyperAutoAgent 创建成功

5. 集成测试:
   ✓ _execute_hyperauto_task 参数: ['ctx', 'task_id', 'task_description']
   ✓ _execute_hyperauto_task 是异步方法: True

✅ 所有测试通过！
```

## 修复文件

- **文件**: `openlaoke/commands/hyperauto_command.py`
- **行数**: 第 719 行
- **修改**: `timeout_seconds` → `timeout_per_task`

## 验证清单

- [x] Python 编译检查通过
- [x] 参数名修复正确
- [x] HAutoConfig 创建成功
- [x] HyperAutoAgent 创建成功
- [x] 任务启动成功
- [x] 进度查看成功
- [x] 任务停止成功
- [x] 所有单元测试通过
- [x] 所有集成测试通过

## 版本信息

- **修复版本**: v0.1.11
- **修复日期**: 2026-04-04
- **修复内容**: HyperAutoConfig 参数错误
- **影响范围**: `/hyperauto` 命令

## 相关文档

- `openlaoke/core/hyperauto/config.py` - HyperAutoConfig 定义
- `openlaoke/core/hyperauto/agent.py` - HyperAutoAgent 实现
- `openlaoke/commands/hyperauto_command.py` - HyperAuto 命令

## 后续改进

1. **参数验证**: 在创建配置前验证参数
2. **错误提示**: 提供更友好的错误信息
3. **类型检查**: 使用 mypy 严格模式检查参数类型
4. **单元测试**: 添加参数验证的单元测试

## 教训总结

1. **必须测试**: 任何代码修改都必须经过完整测试
2. **参数检查**: 使用新类时必须查看正确的参数名
3. **错误处理**: 提供清晰的错误信息帮助调试
4. **代码审查**: 重要修改需要代码审查
