"""Demonstration: Building a complete project with gemma3:1b.

This demo shows how to build a simple calculator module using
the incremental workflow with a small model (gemma3:1b).

The project is broken down into atomic tasks that the small model
can reliably implement, then assembled into a working module.
"""

import tempfile
from pathlib import Path

from openlaoke.core.architecture import (
    create_decomposer_for_model,
    create_orchestrator_for_model,
)
from openlaoke.core.model_assessment.types import ModelTier
from openlaoke.core.state import create_app_state


def demonstrate_small_model_development():
    """Complete workflow for small model development."""

    print("=" * 80)
    print("🚀 小模型增量式开发演示 - gemma3:1b构建完整项目")
    print("=" * 80)
    print()

    # 定义项目规格
    project_spec = {
        "name": "calculator",
        "description": "Simple calculator module with basic operations",
        "modules": [
            {
                "name": "calculator",
                "description": "Calculator module with basic math operations",
                "dependencies": [],
                "complexity": 5,
                "components": [
                    {
                        "name": "add",
                        "type": "function",
                        "description": "Add two numbers",
                        "inputs": {"a": {"type": "float"}, "b": {"type": "float"}},
                        "outputs": {"type": "float"},
                    },
                    {
                        "name": "subtract",
                        "type": "function",
                        "description": "Subtract two numbers",
                        "inputs": {"a": {"type": "float"}, "b": {"type": "float"}},
                        "outputs": {"type": "float"},
                    },
                    {
                        "name": "multiply",
                        "type": "function",
                        "description": "Multiply two numbers",
                        "inputs": {"a": {"type": "float"}, "b": {"type": "float"}},
                        "outputs": {"type": "float"},
                    },
                    {
                        "name": "divide",
                        "type": "function",
                        "description": "Divide two numbers with error handling",
                        "inputs": {"a": {"type": "float"}, "b": {"type": "float"}},
                        "outputs": {"type": "float"},
                        "complexity": 8,
                    },
                ],
            }
        ],
    }

    print("📋 项目规格 (Project Specification):")
    print(f"  Name: {project_spec['name']}")
    print(f"  Description: {project_spec['description']}")
    print(f"  Modules: {len(project_spec['modules'])}")
    print()

    # 创建临时工作目录
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"📁 工作目录: {tmpdir}")
        print()

        # 创建应用状态
        app_state = create_app_state(cwd=tmpdir)

        # 模型配置
        model = "gemma3:1b"
        print(f"🤖 使用模型: {model}")
        print("  层级: Tier 5 (Limited)")
        print("  最大代码行数: 15行/任务")
        print("  最大参数数量: 3个/函数")
        print("  最大重试次数: 8次")
        print()

        # 创建分解器
        decomposer = create_decomposer_for_model(ModelTier.TIER_5_LIMITED)

        print("🔨 任务分解 (Task Decomposition):")
        print()

        # 分解项目
        task_graph = decomposer.decompose_project(project_spec)

        print(f"  总任务数: {len(task_graph.tasks)}")
        print()

        print("  任务列表 (Task List):")
        for task_id, task in task_graph.tasks.items():
            deps_str = f" [依赖: {', '.join(task.dependencies)}]" if task.dependencies else ""
            test_str = " ✓需要测试" if task.test_required else ""
            print(f"    • {task_id}: {task.description[:50]}")
            print(f"      预估行数: {task.estimated_lines}{test_str}{deps_str}")
        print()

        # 创建编排器
        orchestrator = create_orchestrator_for_model(app_state, model)

        # 创建工作流
        workflow = orchestrator.create_workflow(project_spec)

        print("⚙️  开始执行工作流 (Starting Workflow Execution):")
        print()

        # 执行工作流
        result = orchestrator.execute_workflow(workflow.workflow_id)

        # 显示进度
        progress = workflow.get_progress()
        print(f"  进度: {progress['progress_percentage']:.1f}%")
        print(f"  完成: {progress['completed']}/{progress['total_steps']}")
        print(f"  失败: {progress['failed']}")
        print()

        # 显示结果
        if result.success:
            print("✅ 工作流执行成功!")
            print()
            print("📝 生成的代码 (Generated Code):")
            print("-" * 80)
            print(result.code)
            print("-" * 80)
            print()

            # 保存代码
            output_file = Path(tmpdir) / "calculator.py"
            output_file.write_text(result.code)
            print(f"💾 代码已保存到: {output_file}")
            print()

            # 显示测试结果
            if result.test_results:
                print("🧪 测试结果 (Test Results):")
                for test_id, passed in result.test_results.items():
                    status = "✅ PASSED" if passed else "❌ FAILED"
                    print(f"  • {test_id}: {status}")
                print()
        else:
            print("❌ 工作流执行失败")
            print()
            print("错误信息:")
            for error in result.errors:
                print(f"  • {error}")
            print()

        # 显示详细状态
        workflow_status = orchestrator.get_workflow_status(workflow.workflow_id)
        if workflow_status:
            print("📊 工作流详细状态:")
            print(f"  模型: {workflow_status['model']}")
            print(f"  层级: {workflow_status['model_tier']}")
            print()

            print("  步骤详情:")
            for step in workflow_status["steps"]:
                status_emoji = {
                    "completed": "✅",
                    "failed": "❌",
                    "pending": "⏳",
                    "in_progress": "⚙️",
                    "retrying": "🔄",
                }.get(step["status"], "❓")

                print(f"    {status_emoji} {step['step_id']}: {step['status']}")
                print(f"       尝试次数: {step['attempts']}/{step['max_attempts']}")
                if step["error"]:
                    print(f"       错误: {step['error']}")
            print()

        # 保存工作流状态
        orchestrator.save_workflow_state(workflow.workflow_id)
        print("💾 工作流状态已保存")
        print()

    print("=" * 80)
    print("🎯 关键特性演示:")
    print("=" * 80)
    print()
    print("1. ✅ 原子化任务拆解")
    print("   - 每个函数最多15行代码")
    print("   - 最多3个参数")
    print("   - 复杂函数拆解成子任务")
    print()
    print("2. ✅ 增量式开发")
    print("   - 任务按依赖关系排序")
    print("   - 逐步实现和验证")
    print("   - 失败自动重试(最多8次)")
    print()
    print("3. ✅ 标准化接口")
    print("   - 统一的API规范")
    print("   - 标准化代码模板")
    print("   - 自动生成文档字符串")
    print()
    print("4. ✅ 自动组装验证")
    print("   - 语法检查")
    print("   - 类型检查")
    print("   - 测试验证")
    print()
    print("5. ✅ 完整的工作流管理")
    print("   - 状态持久化")
    print("   - 进度跟踪")
    print("   - 错误恢复")
    print()
    print("🎉 演示完成！小模型可以可靠地构建完整项目！")
    print()


if __name__ == "__main__":
    demonstrate_small_model_development()
