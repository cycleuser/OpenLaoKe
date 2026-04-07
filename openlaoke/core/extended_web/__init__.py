"""Extended Web providers - Browser-based authentication for free AI services.

This module provides browser-based authentication for various Web AI services,
similar to ZeroToken approach. It uses Playwright to capture cookies and tokens
from logged-in browser sessions.

Supported providers:
- DeepSeek Web (chat.deepseek.com)
- Claude Web (claude.ai)
- ChatGPT Web (chat.openai.com)
- Qwen Web (tongyi.aliyun.com)
- Kimi Web (kimi.moonshot.cn)
- Gemini Web (gemini.google.com)
- Grok Web (grok.x.ai)
- Doubao Web (doubao.com)
- GLM Web (chatglm.cn)
"""

from .browser_auth import BrowserAuthManager
from .deepseek_client import DeepSeekWebClient
from .types import WebProviderConfig, AuthResult

__all__ = [
    "BrowserAuthManager",
    "DeepSeekWebClient",
    "WebProviderConfig",
    "AuthResult",
]
