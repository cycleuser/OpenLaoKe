#!/usr/bin/env python3
"""Test Extended Web API calls."""

import asyncio
from openlaoke.core.extended_web.providers_api import ExtendedWebClient

async def test_deepseek():
    """Test DeepSeek API."""
    print("Testing DeepSeek API...")
    
    client = ExtendedWebClient("deepseek-chat")
    
    try:
        messages = [{"role": "user", "content": "你好，请自我介绍"}]
        response = await client.chat(messages)
        
        print(f"✓ Response received")
        print(f"  Content: {response.get('content', '')[:100]}...")
        print(f"  Model: {response.get('model', 'unknown')}")
        print(f"  Usage: {response.get('usage', {})}")
        
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        await client.close()

if __name__ == "__main__":
    result = asyncio.run(test_deepseek())
    if result:
        print("\n✅ Test passed!")
    else:
        print("\n❌ Test failed - authentication required")
        print("Run: python3 quick_auth.py deepseek-chat")
