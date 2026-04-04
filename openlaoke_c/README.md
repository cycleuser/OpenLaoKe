# OpenLaoKe C

C语言版本的OpenLaoKe - 开源AI编程助手。

## 特性

- 完整的类型系统定义
- 工具注册和执行框架
- 状态管理和持久化
- 多提供商API客户端接口
- REPL交互式命令行

## 编译

```bash
make
```

## 运行

```bash
./bin/openlaoke
```

## 命令行选项

```bash
./bin/openlaoke --help
```

## 交互命令

- `/help` - 显示帮助
- `/status` - 显示当前状态
- `/tools` - 列出可用工具
- `/exit` - 退出程序

## 项目结构

```
openlaoke_c/
├── include/          # 头文件
│   ├── types.h       # 类型定义
│   ├── state.h       # 状态管理
│   ├── tool_registry.h  # 工具注册
│   ├── tools.h       # 工具接口
│   ├── api_client.h  # API客户端
│   └── repl.h        # REPL接口
├── core/             # 核心实现
│   ├── state.c
│   └── tool_registry.c
├── tools/            # 工具实现
│   └── tools.c
├── types/            # 类型实现
│   └── types.c
├── main.c            # 主程序
├── Makefile          # 构建配置
└── README.md         # 本文件
```

## 开发状态

已实现:
- ✅ 核心类型定义
- ✅ 工具注册框架
- ✅ 状态管理
- ✅ Bash/Read/Write/ls 工具
- ✅ REPL主循环
- ✅ 命令行解析

待实现:
- ⏳ API客户端实现
- ⏳ 更多工具 (Glob, Grep, Git, etc.)
- ⏳ 配置文件加载
- ⏳ 会话持久化
- ⏳ 多线程支持

## 依赖

- GCC 或 Clang
- libcURL (HTTP请求)
- libjansson (JSON解析)
- pthreads (多线程)

## 许可

MIT License