# OpenLaoKe 多语言代码能力增强设计方案

## 背景与目标

OpenLaoKe 当前已具备基础的 Bash/Read/Write/Edit 等工具，但在**代码生成质量、多语言支持、安全执行**方面仍有短板。本方案目标：

1. **小模型友好**：通过结构化输出、静态分析前置校验、错误信息回传，使 3B-14B 模型也能产出高质量 Python/C/Rust 代码。
2. **三种语言 state-of-the-art 能力**：Python（解释型+丰富生态）、C（系统级+编译型）、Rust（内存安全+现代语法）。
3. **安全沙箱优先**：所有代码执行默认在受限环境中，防止破坏性操作。

## 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│  对话层 (REPL / Web UI / Agent)                        │
│  "写一个 Python 脚本统计词频"                             │
└──────────────────────┬────────────────────────────────────┘
                           │ /run_code (CodeRunner Tool)
                           ▼
┌──────────────────────▼────────────────────────────────────┐
│  LangRegistry (语言治理)                                │
│  - LanguageSpec (语言规格)                            │
│  - 注册/查询/扩展                                  │
└──────────────────────┬────────────────────────────────────┘
                           │
          ┌────────────▼──────────┐  ┌────────────▼──────────┐  ┌────────────▼──────────┐
          │ PythonSubsystem  │  │   CSubsystem    │  │  RustSubsystem  │
          │ - sandbox      │  │   - sandbox     │  │   - sandbox     │
          │ - static anal │  │   - compile    │  │   - cargo test  │
          │ - pytest     │  │   - ctest      │  │   - clippy      │
          └─────────────────┘  └─────────────────┘  └─────────────────┘
                           │
          ┌────────────▼────────────────────┐
          │  Sandbox Abstraction (安全执行)      │
          │  - SubprocessSandbox (Phase 0)        │
          │  - ContainerSandbox (Phase 1)        │
          │  - SeccompSandbox (Phase 1)         │
          └────────────────────────────────────┘
```

## 核心数据结构

### LanguageSpec

```python
# openlaoke/core/langs/spec.py

@dataclass
class LanguageSpec:
    name: str                  # "python", "c", "rust"
    display_name: str          # "Python", "C", "Rust"
    extensions: list[str]        # [".py", ".pyi"]
    compiler: str | None      # "python3", "clang", "rustc"
    interpreter: str | None    # "python3", None, None
    test_runner: str | None  # "pytest", "ctest", "cargo test"
    static_analyzers: list[str]  # ["mypy", "ruff"], ["clang-tidy"], ["rust-analyzer", "clippy"]
    sandbox_kind: str         # "subprocess", "container", "seccomp"
    allowed_ops: dict[str, bool]  # {"file_read": True, "file_write": True, "network": False}
    default_timeout_ms: int = 30000
    default_mem_mb: int = 256
```

### LangRegistry

```python
class LangRegistry:
    _specs: dict[str, LanguageSpec]
    _lock: asyncio.Lock

    def register(spec: LanguageSpec) -> None
    def get_spec(name: str) -> LanguageSpec | None
    def list_supported() -> list[str]
    def is_supported(name: str) -> bool
```

## 各语言子系统设计

### Python 子系统（Phase 0 优先实现）

| 能力 | 实现 | 小模型优化 |
|------|------|--------------|
| 代码执行 | SubprocessSandbox: `python3 <file>` | 捕获 stdout/stderr，返回结构化错误 |
| 静态分析 | mypy + ruff（可选 pylint） | 将 warning 级别信息回传给 LLM 用于改进 |
| 单元测试 | pytest（自动发现 test_*.py） | 提供最小用例模板给 LLM |
| 类型检查 | mypy --strict（可选） | 类型错误是 LLM 的重要改进信号 |

### C 子系统（Phase 1）

| 能力 | 实现 | 小模型优化 |
|------|------|--------------|
| 编译 | clang -Wall -Wextra -fsanitize=address | 编译错误逐行回传 |
| 执行 | SubprocessSandbox with seccomp | 限制系统调用 |
| 静态分析 | clang-tidy, cppcheck | 内存安全警告重点回传 |
| 单元测试 | ctest（CMake）或自定义 runner | 提供 Makefile 模板 |

### Rust 子系统（Phase 1）

| 能力 | 实现 | 小模型优化 |
|------|------|--------------|
| 编译/检查 | cargo check, cargo clippy | warning 重点回传 |
| 测试 | cargo test | 测试失败信息结构化 |
| 静态分析 | rust-analyzer (LSP) | 类型推断错误重点 |
| 安全 | unsafe 块检测，依赖审计 | 提示 LLM 避免 unsafe |

## 安全沙箱设计

### 目标能力

1. **隔离**：代码在受限环境中执行，无法访问主机敏感文件
2. **资源限制**：CPU 时间、内存、输出大小、文件写入
3. **可观测**：执行时间、内存使用、退出码、stdout/stderr
4. **可替换**：Phase 0 用 subprocess，Phase 1 支持容器/seccomp

### Sandbox 接口

```python
class SandboxResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    exec_ms: float
    mem_kb: int | None
    artifacts: list[str]  # 生成物路径

class SandboxBase(ABC):
    @abstractmethod
    async def run(self, code: str, timeout_ms: int, mem_mb: int, workdir: str) -> SandboxResult
```

### Phase 0 实现：SubprocessSandbox

- 写入临时文件
- 用 `subprocess.run()` 执行，resource limits via `ulimit` or `prlimit`
- 捕获 stdout/stderr
- 清理临时文件

### Phase 1 升级：ContainerSandbox / SeccompSandbox

- 用 `bubblewrap` (Linux) 或 `Docker` 做文件系统隔离
- 用 `seccomp` 限制系统调用（禁止 execve, mount, etc.）
- macOS 上 Phase 0 保持 subprocess，后续可考虑 `sandbox-exec` 替代

## 与现有系统集成

### 1. CodeRunner Tool（新增）

```python
class CodeRunnerInput(BaseModel):
    language: Literal["python", "c", "rust"]
    code: str
    test_code: str | None = None
    timeout_ms: int | None = None
    mem_mb: int | None = None
```

- 注册为 `code_runner` 工具
- 调用 LangRegistry → 对应子系统 → Sandbox
- 返回结构化 ToolResultBlock

### 2. REPL 集成

- 对话流：`用户输入 → LLM 生成代码 → CodeRunner Tool 执行 → 结果回传给 LLM → LLM 改进代码`
- 支持多轮迭代：若执行失败，让 LLM 基于错误信息改进

### 3. Agent 集成

- Agent 工具调用链中可调用 CodeRunner
- 支持多步骤任务（生成 → 编译 → 测试 → 提交）

## 分阶段实施计划

### Phase 0（本周，最小可用）
- [x] Patch A: 创建 `openlaoke/core/langs/` 模块，定义 LanguageSpec、LangRegistry
- [x] Patch B: 实现 PythonSandbox（subprocess 最小实现）
- [x] Patch C: 实现 CodeRunner Tool（支持 Python）
- [x] Patch D: 注册到工具系统，连接到 REPL
- [x] Patch E: 基础测试（注册、执行、错误路径）

### Phase 1（下周，三语言 + 安全升级）
- [ ] 升级 Python 沙箱（seccomp/bubblewrap）
- [ ] 实现 C 子系统（clang + subprocess 沙箱）
- [ ] 实现 Rust 子系统（cargo + subprocess 沙箱）
- [ ] 增加静态分析集成（mypy/ruff/clang-tidy/clippy）
- [ ] 增加单元测试模板和自动运行

### Phase 2（后续，闭环与质量）
- [ ] 对话-代码闭环（自动迭代改进）
- [ ] 结构化输出（JSON 格式的执行报告）
- [ ] 基准测试与评估（正确性、性能、安全）
- [ ] 容器化沙箱（Docker/Podman 支持）

## 风险与对策

| 风险 | 对策 |
|------|------|
| 沙箱逃逸 | Phase 0 限制文件系统访问 + 超时；Phase 1 引入容器化 |
| 小模型输出质量差 | 结构化错误信息回传 + 静态分析前置 + 多轮迭代 |
| 依赖安装困难 | 提供清晰的依赖检查 + 错误提示；优先系统已有工具 |
| 多语言扩展复杂度 | 统一 LanguageSpec 接口；每语言一个子系统文件 |
| macOS 沙箱能力弱 | Phase 0 用 subprocess；标注 macOS 沙箱限制；后续调研 solutions |

## 补丁清单（Phase 0）

1. **Patch A**: `openlaoke/core/langs/__init__.py` + `spec.py` — LanguageSpec、LangRegistry
2. **Patch B**: `openlaoke/core/langs/python_sandbox.py` — Python 最小沙箱
3. **Patch C**: `openlaoke/tools/code_runner.py` — CodeRunner Tool
4. **Patch D**: 更新 `openlaoke/tools/register.py` — 注册 code_runner
5. **Patch E**: `tests/test_multilang.py` — 基础测试

---

*设计文档版本：2026-05-02*
*对应实施：Phase 0 最小可用版本*
