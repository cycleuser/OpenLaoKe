"""Type definitions for extended web providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


WebProviderType = Literal[
    "deepseek-chat",
    "deepseek-coder",
    "claude-web",
    "chatgpt-web",
    "qwen-web",
    "kimi-web",
    "gemini-web",
    "grok-web",
    "doubao-web",
    "glm-web",
]


@dataclass
class WebProviderConfig:
    """Configuration for a web-based AI provider."""

    provider_type: WebProviderType
    name: str
    base_url: str
    login_url: str
    api_endpoint: str
    cookie_domains: list[str]
    required_cookies: list[str]
    bearer_token: bool = False
    custom_headers: dict[str, str] = field(default_factory=dict)


# Provider configurations
WEB_PROVIDERS: dict[WebProviderType, WebProviderConfig] = {
    "deepseek-chat": WebProviderConfig(
        provider_type="deepseek-chat",
        name="DeepSeek Chat",
        base_url="https://chat.deepseek.com",
        login_url="https://chat.deepseek.com/login",
        api_endpoint="https://chat.deepseek.com/api/v1/chat/completions",
        cookie_domains=["chat.deepseek.com", "deepseek.com"],
        required_cookies=["d_id", "ds_session_id"],
        bearer_token=False,
        custom_headers={
            "Referer": "https://chat.deepseek.com/",
            "Origin": "https://chat.deepseek.com",
        },
    ),
    "deepseek-coder": WebProviderConfig(
        provider_type="deepseek-coder",
        name="DeepSeek Coder",
        base_url="https://chat.deepseek.com",
        login_url="https://chat.deepseek.com/login",
        api_endpoint="https://chat.deepseek.com/api/v1/chat/completions",
        cookie_domains=["chat.deepseek.com", "deepseek.com"],
        required_cookies=["d_id", "ds_session_id"],
        bearer_token=False,
        custom_headers={
            "Referer": "https://chat.deepseek.com/",
            "Origin": "https://chat.deepseek.com",
        },
    ),
    "claude-web": WebProviderConfig(
        provider_type="claude-web",
        name="Claude Web",
        base_url="https://claude.ai",
        login_url="https://claude.ai/login",
        api_endpoint="https://claude.ai/api/organizations",
        cookie_domains=["claude.ai"],
        required_cookies=["session_id"],
        bearer_token=False,
        custom_headers={
            "Referer": "https://claude.ai/",
            "Origin": "https://claude.ai",
        },
    ),
    "chatgpt-web": WebProviderConfig(
        provider_type="chatgpt-web",
        name="ChatGPT Web",
        base_url="https://chat.openai.com",
        login_url="https://chat.openai.com/auth/login",
        api_endpoint="https://chat.openai.com/backend-api/conversation",
        cookie_domains=["openai.com"],
        required_cookies=["__Secure-next-auth.session-token"],
        bearer_token=True,
        custom_headers={
            "Referer": "https://chat.openai.com/",
            "Origin": "https://chat.openai.com",
        },
    ),
    "qwen-web": WebProviderConfig(
        provider_type="qwen-web",
        name="Qwen Web (通义千问)",
        base_url="https://tongyi.aliyun.com",
        login_url="https://tongyi.aliyun.com/login",
        api_endpoint="https://tongyi.aliyun.com/api/chat",
        cookie_domains=["aliyun.com", "taobao.com"],
        required_cookies=["_tb_token_", "cookie2"],
        bearer_token=False,
        custom_headers={
            "Referer": "https://tongyi.aliyun.com/",
            "Origin": "https://tongyi.aliyun.com",
        },
    ),
    "kimi-web": WebProviderConfig(
        provider_type="kimi-web",
        name="Kimi Web (月之暗面)",
        base_url="https://kimi.moonshot.cn",
        login_url="https://kimi.moonshot.cn/login",
        api_endpoint="https://kimi.moonshot.cn/api/chat",
        cookie_domains=["moonshot.cn"],
        required_cookies=["kimi_token"],
        bearer_token=False,
        custom_headers={
            "Referer": "https://kimi.moonshot.cn/",
            "Origin": "https://kimi.moonshot.cn",
        },
    ),
    "gemini-web": WebProviderConfig(
        provider_type="gemini-web",
        name="Gemini Web",
        base_url="https://gemini.google.com",
        login_url="https://accounts.google.com/login",
        api_endpoint="https://gemini.google.com/_b/AIzaSy...",
        cookie_domains=["google.com", "gemini.google.com"],
        required_cookies=["__Secure-1PSID", "__Secure-3PSID"],
        bearer_token=False,
        custom_headers={
            "Referer": "https://gemini.google.com/",
            "Origin": "https://gemini.google.com",
        },
    ),
    "grok-web": WebProviderConfig(
        provider_type="grok-web",
        name="Grok Web",
        base_url="https://grok.x.ai",
        login_url="https://grok.x.ai/login",
        api_endpoint="https://grok.x.ai/api/chat",
        cookie_domains=["x.ai", "grok.x.ai"],
        required_cookies=["auth_token"],
        bearer_token=True,
        custom_headers={
            "Referer": "https://grok.x.ai/",
            "Origin": "https://grok.x.ai",
        },
    ),
    "doubao-web": WebProviderConfig(
        provider_type="doubao-web",
        name="Doubao Web (豆包)",
        base_url="https://doubao.com",
        login_url="https://doubao.com/login",
        api_endpoint="https://doubao.com/api/chat",
        cookie_domains=["doubao.com", "byteimg.com"],
        required_cookies=["doubao_token"],
        bearer_token=False,
        custom_headers={
            "Referer": "https://doubao.com/",
            "Origin": "https://doubao.com",
        },
    ),
    "glm-web": WebProviderConfig(
        provider_type="glm-web",
        name="GLM Web (智谱清言)",
        base_url="https://chatglm.cn",
        login_url="https://chatglm.cn/login",
        api_endpoint="https://chatglm.cn/api/chat",
        cookie_domains=["chatglm.cn"],
        required_cookies=["glmsession"],
        bearer_token=False,
        custom_headers={
            "Referer": "https://chatglm.cn/",
            "Origin": "https://chatglm.cn",
        },
    ),
}


@dataclass
class AuthResult:
    """Result of browser-based authentication."""

    provider_type: WebProviderType
    cookie: str
    bearer_token: str = ""
    user_agent: str = ""
    additional_headers: dict[str, str] = field(default_factory=dict)
    expires_at: int | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "provider_type": self.provider_type,
            "cookie": self.cookie,
            "bearer_token": self.bearer_token,
            "user_agent": self.user_agent,
            "additional_headers": self.additional_headers,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AuthResult:
        """Create from dictionary."""
        return cls(
            provider_type=data["provider_type"],
            cookie=data["cookie"],
            bearer_token=data.get("bearer_token", ""),
            user_agent=data.get("user_agent", ""),
            additional_headers=data.get("additional_headers", {}),
            expires_at=data.get("expires_at"),
        )
