"""Test if current model supports tools."""
import asyncio

from openlaoke.core.multi_provider_api import MultiProviderClient
from openlaoke.types.providers import MultiProviderConfig


async def test_model():
    config = MultiProviderConfig.defaults()
    client = MultiProviderClient(config)

    # Test gemma3:1b
    model = "gemma3:1b"
    print(f"Testing {model}...")

    try:
        # Try a simple request without tools
        response, _, _ = await client.send_message(
            "You are helpful.",
            [{"role": "user", "content": "Calculate 2+2"}],
            None,  # No tools
            model
        )
        print(f"✓ {model} works without tools")
        print(f"Response: {response.content[:100]}")
    except Exception as e:
        print(f"✗ {model} failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_model())
