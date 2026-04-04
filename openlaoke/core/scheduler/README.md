# Task Scheduler System

任务调度和超时控制系统，用于管理并发任务执行。

## 模块结构

```
openlaoke/core/scheduler/
├── __init__.py          # 模块导出
├── scheduler.py         # TaskScheduler主调度器
├── executor.py          # TaskExecutor任务执行器
├── timeout.py           # TimeoutHandler超时控制
└── priority.py          # PriorityQueue优先级队列
```

## 核心组件

### TaskScheduler

主调度器，管理并发任务执行：

```python
from openlaoke.core.scheduler import TaskScheduler
from openlaoke.types.core_types import TaskStatus

# 创建调度器
scheduler = TaskScheduler(
    max_concurrent=3,      # 最大并发数
    default_timeout=900.0  # 默认超时（15分钟）
)

# 启动调度器
await scheduler.start()

# 提交任务
def my_task(x: int) -> int:
    return x * 2

result = await scheduler.submit(
    my_task,
    5,                     # 参数
    priority=0,            # 优先级（越小越优先）
    timeout=60.0,          # 超时时间
)

print(result.status)       # TaskStatus.COMPLETED
print(result.result)       # 10

# 批量提交
tasks = [(my_task, (i,), {}) for i in range(10)]
results = await scheduler.submit_batch(
    tasks,
    parallel=True,         # 并行执行
    timeout=30.0,
)

# 取消任务
await scheduler.cancel(task_id)

# 获取状态
status = await scheduler.get_status(task_id)

# 关闭调度器
await scheduler.shutdown()
```

### TimeoutHandler

超时控制处理器：

```python
from openlaoke.core.scheduler import TimeoutHandler

handler = TimeoutHandler(default_timeout=900.0)

# 带超时执行协程
async def my_coro():
    await asyncio.sleep(1)
    return "done"

result = await handler.with_timeout(
    my_coro(),
    timeout=60.0,
    task_id="task_123"
)

# 设置超时回调
def on_timeout():
    print("Task timed out!")

handler.set_timeout("task_id", 30.0, on_timeout)

# 延长超时
await handler.extend_timeout("task_id", additional=60.0)

# 取消超时
handler.cancel_timeout("task_id")
```

### TaskExecutor

任务执行器，支持重试和超时：

```python
from openlaoke.core.scheduler import TaskExecutor

executor = TaskExecutor(
    max_workers=3,
    max_retries=3,
    retry_delay=1.0
)

# 执行同步函数
result = await executor.execute(
    "task_id",
    my_function,
    *args,
    timeout=60.0,
    retries=3,
    **kwargs
)

# 执行异步函数
result = await executor.execute_async(
    "task_id",
    my_coroutine(),
    timeout=30.0
)

# 取消任务
executor.cancel("task_id")

# 关闭执行器
executor.shutdown()
```

### PriorityQueue

线程安全的优先级队列：

```python
from openlaoke.core.scheduler import PriorityQueue

queue = PriorityQueue(maxsize=100)

# 添加任务（priority越小越优先）
queue.put(item, priority=0)   # 高优先级
queue.put(item, priority=10)  # 低优先级

# 获取任务
item = queue.get()

# 查看队首
item = queue.peek()

# 查询大小
size = queue.qsize()
is_empty = queue.empty()
is_full = queue.full()

# 清空队列
queue.clear()
```

## 数据结构

### ScheduledTask

```python
@dataclass
class ScheduledTask:
    id: str                    # 任务ID
    func: Any                  # 函数或协程
    args: tuple                # 参数
    kwargs: dict               # 关键字参数
    priority: int              # 优先级
    timeout: float | None      # 超时时间
    status: TaskStatus         # 状态
    result: Any | None         # 结果
    error: str | None          # 错误信息
    started_at: float | None   # 开始时间
    completed_at: float | None # 完成时间
    retries: int               # 重试次数
```

### TaskResult

```python
@dataclass
class TaskResult:
    task_id: str               # 任务ID
    status: TaskStatus         # 状态
    result: Any | None         # 结果
    error: str | None          # 错误信息
    duration: float | None     # 执行时长
```

## 配置常量

参考 Deer Flow 项目：

```python
MAX_CONCURRENT = 3            # 最大并发任务数
DEFAULT_TIMEOUT = 15 * 60     # 默认超时（15分钟）
MAX_RETRIES = 3               # 最大重试次数
RETRY_DELAY = 1.0             # 重试延迟（秒）
```

## 使用示例

### 1. 并发执行多个任务

```python
async def main():
    scheduler = TaskScheduler(max_concurrent=5)
    await scheduler.start()
    
    tasks = [
        (process_file, (f,), {})
        for f in files
    ]
    
    results = await scheduler.submit_batch(
        tasks,
        parallel=True,
        timeout=60.0
    )
    
    for result in results:
        if result.status == TaskStatus.COMPLETED:
            print(f"Success: {result.result}")
        else:
            print(f"Failed: {result.error}")
    
    await scheduler.shutdown()
```

### 2. 带优先级的任务队列

```python
async def main():
    scheduler = TaskScheduler()
    await scheduler.start()
    
    # 高优先级任务
    await scheduler.submit(
        urgent_task,
        priority=0,
        timeout=30.0
    )
    
    # 低优先级任务
    await scheduler.submit(
        background_task,
        priority=10,
        timeout=300.0
    )
    
    await scheduler.shutdown()
```

### 3. 带重试的任务执行

```python
async def main():
    scheduler = TaskScheduler()
    await scheduler.start()
    
    result = await scheduler.submit(
        unreliable_api_call,
        retries=3,          # 重试3次
        timeout=60.0,
    )
    
    await scheduler.shutdown()
```

## 状态管理

任务状态使用 `TaskStatus` 枚举：

- `PENDING`: 待执行
- `RUNNING`: 正在执行
- `COMPLETED`: 已完成
- `FAILED`: 失败
- `KILLED`: 已终止

## 统计信息

```python
stats = scheduler.get_stats()
print(stats)
# {
#     "queue_size": 5,
#     "pending": 2,
#     "running": 3,
#     "completed": 10,
#     "failed": 1,
#     "killed": 0,
#     "total": 16,
#     "results": 11
# }
```

## 测试

```bash
pytest tests/test_scheduler.py -v
```

## 注意事项

1. 必须调用 `await scheduler.start()` 启动调度器
2. 使用完毕后调用 `await scheduler.shutdown()` 关闭
3. 优先级越小越优先（0 > 5 > 10）
4. 超时会将任务状态设为 FAILED
5. 所有异步操作需要在 async 环境中执行