#!/usr/bin/env python3
"""测试 OpenLaoKe 的免费模型功能"""

import asyncio

from openlaoke.core.multi_provider_api import MultiProviderClient
from openlaoke.types.providers import MultiProviderConfig


async def test_free_model(model: str, prompt: str = "你好") -> None:
    """测试单个免费模型"""
    config = MultiProviderConfig.defaults()
    config.active_provider = "opencode"
    config.active_model = model

    client = MultiProviderClient(config)

    try:
        messages = [{"role": "user", "content": prompt}]
        response, usage, cost = await client.send_message(
            system_prompt="你是一个有用的 AI 助手", messages=messages, model=model, max_tokens=100
        )
        print(f"✓ {model}: {response.content[:50] if response.content else 'No content'}...")
        print(f"  Token: 输入={usage.input_tokens}, 输出={usage.output_tokens}")
        print(f"  费用：输入=${cost.input_cost:.6f}, 输出=${cost.output_cost:.6f}")
    except Exception as e:
        print(f"✗ {model}: {str(e)[:100]}")
    finally:
        await client.close()


async def main():
    """测试所有免费模型"""
    print("=" * 60)
    print("OpenLaoKe 免费模型测试")
    print("=" * 60)

    free_models = [
        "big-pickle",
        "mimo-v2-flash-free",
        "gpt-5-nano",
    ]

    for model in free_models:
        await test_free_model(model)
        print()

    print("=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
