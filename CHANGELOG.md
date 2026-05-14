# Changelog

All notable changes to OpenLaoKe will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added - Research System

#### 溯源验证系统 (Provenance Tracking)
- `openlaoke/core/supervisor/provenance.py` - 完整的溯源追踪系统
  - `ProvenanceRecord` - 研究输出溯源记录，包含证据表、验证状态、来源统计
  - `VerificationStatus` - 验证状态枚举 (PASS / PASS_WITH_NOTES / BLOCKED / UNVERIFIED / INFERRED)
  - `SourceEntry` - 证据表条目，支持来源类型和置信度标记
  - `VerificationCheck` - 验证检查记录
  - 支持 Markdown 导出和加载 (`.provenance.md` 侧车文件)

#### Slug 命名与输出约定
- `openlaoke/core/supervisor/slug_utils.py` - 标准化文件命名
  - `generate_slug()` - 从主题生成短 slug (小写、连字符、过滤虚词、支持中文)
  - `get_output_paths()` - 获取标准输出路径 (plan/draft/cited/output/provenance)
  - `ensure_output_dirs()` - 创建所需目录结构
  - `validate_slug()` - slug 格式验证

#### 研究代理系统
- `openlaoke/core/multi_agent/research_agents.py` - 4 个专用研究子代理
  - `researcher` - 证据收集 (论文、Web、代码库)
  - `reviewer` - 模拟同行评审 (FATAL/MAJOR/MINOR 分级)
  - `writer` - 结构化草稿撰写
  - `verifier` - 引用添加和 URL 验证
  - 每个代理包含完整的 system_prompt 和工具列表

#### 工作流编排器
- `openlaoke/core/multi_agent/research_orchestrator.py` - 研究流程编排
  - `ResearchWorkflowOrchestrator` - 支持 deepresearch/lit/review 三种工作流
  - `WorkflowStep` - 带依赖关系的流程步骤
  - `WorkflowResult` - 工作流结果追踪
  - 自动 provenance 生成和验证状态计算

#### 研究命令
- `openlaoke/commands/research_commands.py` - 新增 4 个斜杠命令
  - `/deepresearch <topic>` - 深度研究，创建计划和溯源文件
  - `/lit <topic>` - 文献综述
  - `/review <artifact>` - 同行评审
  - `/outputs` - 浏览研究产出

#### 实验日志系统
- `openlaoke/core/supervisor/lab_notebook.py` - CHANGELOG 实验室笔记本
  - `LabNotebook` -  chronological 研究进度记录
  - `LabEntry` - 单条日志条目 (时间戳、slug、动作、状态、下一步)
  - 支持文件追加和加载

#### 上下文卫生管理
- `openlaoke/core/supervisor/context_hygiene.py` - 渐进式文件写入
  - `WriteBuffer` - 缓冲区和阈值刷新，避免内存累积
  - `extract_key_quotes()` - 从大内容中提取关键引用

#### 研究技能模板
- `openlaoke/skills/research/` - 4 个研究技能
  - `deep-research/SKILL.md` - 深度研究工作流
  - `literature-review/SKILL.md` - 文献综述
  - `peer-review/SKILL.md` - 同行评审
  - `source-comparison/SKILL.md` - 来源对比
- `openlaoke/core/skill_system.py` - 技能系统增强
  - 支持嵌套技能目录 (`dir/subdir/SKILL.md`)
  - 添加 `openlaoke/skills` 为默认技能目录

#### 类型系统增强
- `openlaoke/types/core_types.py` - `TaskState` 新增字段
  - `slug` - 任务 slug
  - `verification_status` - 验证状态
  - `provenance_file` - 溯源文件路径

#### 监督系统增强
- `openlaoke/core/supervisor/checker.py` - 新增检查类型
  - `provenance_check` - 溯源文件验证
  - `citation_check` - 引用格式和完整性验证
- `openlaoke/core/supervisor/supervisor.py` - 研究类需求自动提取
  - 识别 research/investigate/survey 关键词
  - 自动添加溯源、引用、证据表、验证状态需求

### Changed
- `openlaoke/core/multi_agent/__init__.py` - 导出研究代理和编排器
- `openlaoke/core/supervisor/__init__.py` - 导出所有新模块
- `openlaoke/commands/registry.py` - 注册研究命令

### Tests
- `tests/test_provenance.py` - 24 个测试 (溯源系统)
- `tests/test_slug_utils.py` - 15 个测试 (Slug 和路径)
- `tests/test_lab_notebook.py` - 10 个测试 (实验日志)
- `tests/test_context_hygiene.py` - 8 个测试 (上下文卫生)
- `tests/test_research_agents.py` - 14 个测试 (研究代理)
- `tests/test_research_orchestrator.py` - 15 个测试 (工作流编排)
- `tests/test_research_commands.py` - 10 个测试 (研究命令)
- 总计新增 **96 个测试**，全部通过
