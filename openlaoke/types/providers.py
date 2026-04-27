"""Provider types and configurations for multiple LLM backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ProviderType(StrEnum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"
    OLLAMA = "ollama"
    LM_STUDIO = "lm_studio"
    MINIMAX = "minimax"
    ALIYUN_CODING_PLAN = "aliyun_coding_plan"
    AZURE_OPENAI = "azure_openai"
    GOOGLE = "google"
    GOOGLE_VERTEX = "google_vertex"
    AWS_BEDROCK = "aws_bedrock"
    XAI = "xai"
    MISTRAL = "mistral"
    GROQ = "groq"
    CEREBRAS = "cerebras"
    COHERE = "cohere"
    DEEPINFRA = "deepinfra"
    TOGETHERAI = "togetherai"
    PERPLEXITY = "perplexity"
    OPENROUTER = "openrouter"
    GITHUB_COPILOT = "github_copilot"
    OPENCODE = "opencode"
    LOCAL_BUILTIN = "local_builtin"
    CUSTOM = "custom"


@dataclass
class ProviderConfig:
    """Configuration for a single provider."""

    provider_type: ProviderType
    api_key: str = ""
    base_url: str = ""
    default_model: str = ""
    models: list[str] = field(default_factory=list)
    enabled: bool = True
    is_local: bool = False

    def is_configured(self) -> bool:
        if self.is_local:
            if self.provider_type == ProviderType.LOCAL_BUILTIN:
                from openlaoke.core.local_model_manager import LocalModelManager

                manager = LocalModelManager()
                model_id = self.default_model
                if model_id.startswith("custom:"):
                    path = manager.get_model_path(model_id)
                    return path is not None
                return manager.is_downloaded(model_id)
            return True
        if self.provider_type == ProviderType.OPENCODE:
            return True
        return bool(self.api_key and self.api_key != "none")

    def get_default_model(self) -> str:
        if self.default_model:
            return self.default_model
        return self.models[0] if self.models else ""


@dataclass
class MultiProviderConfig:
    """Configuration for all providers."""

    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    active_provider: str = "ollama"
    active_model: str = ""
    local_n_ctx: int = 262144
    local_repetition_penalty: float = 1.1
    local_temperature: float = 0.3

    @staticmethod
    def _get_local_builtin_models() -> list[str]:
        """Get builtin + custom local model IDs."""
        from openlaoke.utils.config import _get_local_builtin_model_ids

        return _get_local_builtin_model_ids()

    def get_active_provider(self) -> ProviderConfig | None:
        return self.providers.get(self.active_provider)

    def get_active_model(self) -> str:
        if self.active_model:
            return self.active_model
        provider = self.get_active_provider()
        if provider:
            return provider.get_default_model()
        return ""

    def is_configured(self) -> bool:
        provider = self.get_active_provider()
        return provider is not None and provider.is_configured()

    def set_active_provider(self, name: str) -> bool:
        if name in self.providers:
            self.active_provider = name
            return True
        return False

    def list_available_providers(self) -> list[str]:
        return [name for name, p in self.providers.items() if p.is_configured()]

    @staticmethod
    def _detect_ollama_models(base_url: str = "http://localhost:11434") -> list[str]:
        """Try to detect available Ollama models from local installation."""
        try:
            import httpx

            url = f"{base_url}/api/tags"

            with httpx.Client(timeout=3.0) as client:
                response = client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    all_models = [m["name"] for m in data.get("models", [])]

                    # Filter out embedding models
                    embedding_keywords = [
                        "embed",
                        "embedding",
                        "rerank",
                        "reranker",
                        "minilm",
                        "arctic-embed",
                        "bge-",
                        "nomic-embed",
                        "paraphrase",
                        "granite-embedding",
                    ]

                    generation_models = []
                    for model in all_models:
                        model_lower = model.lower()
                        is_embedding = any(kw in model_lower for kw in embedding_keywords)

                        if not is_embedding:
                            generation_models.append(model)

                    return generation_models if generation_models else all_models
        except Exception:
            pass
        return []

    @classmethod
    def defaults(cls) -> MultiProviderConfig:
        # Try to detect Ollama models dynamically
        ollama_models = cls._detect_ollama_models()
        ollama_default = ollama_models[0] if ollama_models else "gemma4:e2b"

        return cls(
            providers={
                "ollama": ProviderConfig(
                    provider_type=ProviderType.OLLAMA,
                    base_url="http://localhost:11434/v1",
                    default_model=ollama_default,
                    models=ollama_models if ollama_models else ["gemma4:e2b"],
                    is_local=True,
                ),
                "lm_studio": ProviderConfig(
                    provider_type=ProviderType.LM_STUDIO,
                    base_url="http://localhost:1234/v1",
                    default_model="local-model",
                    models=["local-model"],
                    is_local=True,
                ),
                "anthropic": ProviderConfig(
                    provider_type=ProviderType.ANTHROPIC,
                    base_url="https://api.anthropic.com",
                    default_model="claude-sonnet-4-20250514",
                    models=[
                        "claude-sonnet-4-20250514",
                        "claude-opus-4-20250514",
                        "claude-3-5-sonnet-20241022",
                        "claude-3-5-haiku-20241022",
                    ],
                ),
                "openai": ProviderConfig(
                    provider_type=ProviderType.OPENAI,
                    base_url="https://api.openai.com/v1",
                    default_model="gpt-4o",
                    models=[
                        "gpt-4o",
                        "gpt-4o-mini",
                        "gpt-4-turbo",
                        "o1-preview",
                        "o1-mini",
                    ],
                ),
                "minimax": ProviderConfig(
                    provider_type=ProviderType.MINIMAX,
                    base_url="https://api.minimaxi.com/v1",
                    default_model="MiniMax-M2.7-highspeed",
                    models=[
                        "MiniMax-M2.7-highspeed",
                        "MiniMax-M2.7",
                        "MiniMax-M2.5-highspeed",
                        "MiniMax-M2.5",
                        "MiniMax-M2.1-highspeed",
                        "MiniMax-M2.1",
                        "MiniMax-M2",
                    ],
                ),
                "aliyun_coding_plan": ProviderConfig(
                    provider_type=ProviderType.ALIYUN_CODING_PLAN,
                    base_url="https://coding.dashscope.aliyuncs.com/v1",
                    default_model="qwen3.5-plus",
                    models=[
                        "qwen3.5-plus",
                        "kimi-k2.5",
                        "glm-5",
                        "MiniMax-M2.5",
                        "qwen3-max-2026-01-23",
                        "qwen3-coder-next",
                        "qwen3-coder-plus",
                        "glm-4.7",
                    ],
                ),
                "openai_compatible": ProviderConfig(
                    provider_type=ProviderType.OPENAI_COMPATIBLE,
                    base_url="",
                    default_model="",
                    models=[],
                ),
                "azure_openai": ProviderConfig(
                    provider_type=ProviderType.AZURE_OPENAI,
                    base_url="",
                    default_model="gpt-4o",
                    models=[
                        "gpt-4o",
                        "gpt-4o-mini",
                        "gpt-4-turbo",
                        "gpt-35-turbo",
                    ],
                ),
                "google": ProviderConfig(
                    provider_type=ProviderType.GOOGLE,
                    base_url="https://generativelanguage.googleapis.com/v1beta",
                    default_model="gemini-2.0-flash",
                    models=[
                        "gemini-2.0-flash",
                        "gemini-2.0-pro",
                        "gemini-1.5-flash",
                        "gemini-1.5-pro",
                    ],
                ),
                "google_vertex": ProviderConfig(
                    provider_type=ProviderType.GOOGLE_VERTEX,
                    base_url="",
                    default_model="gemini-2.0-flash",
                    models=[
                        "gemini-2.0-flash",
                        "gemini-2.0-pro",
                        "gemini-1.5-flash",
                        "gemini-1.5-pro",
                    ],
                ),
                "aws_bedrock": ProviderConfig(
                    provider_type=ProviderType.AWS_BEDROCK,
                    base_url="",
                    default_model="anthropic.claude-3-5-sonnet-20241022-v2:0",
                    models=[
                        "anthropic.claude-3-5-sonnet-20241022-v2:0",
                        "anthropic.claude-3-5-haiku-20241022-v1:0",
                        "anthropic.claude-3-opus-20240229-v1:0",
                        "meta.llama3-1-405b-instruct-v1:0",
                        "meta.llama3-1-70b-instruct-v1:0",
                        "amazon.nova-pro-v1:0",
                        "amazon.nova-lite-v1:0",
                    ],
                ),
                "xai": ProviderConfig(
                    provider_type=ProviderType.XAI,
                    base_url="https://api.x.ai/v1",
                    default_model="grok-2-latest",
                    models=[
                        "grok-2-latest",
                        "grok-2-1212",
                        "grok-beta",
                        "grok-vision-beta",
                    ],
                ),
                "mistral": ProviderConfig(
                    provider_type=ProviderType.MISTRAL,
                    base_url="https://api.mistral.ai/v1",
                    default_model="mistral-large-latest",
                    models=[
                        "mistral-large-latest",
                        "mistral-small-latest",
                        "codestral-latest",
                        "open-mistral-nemo",
                        "open-codestral-mamba",
                    ],
                ),
                "groq": ProviderConfig(
                    provider_type=ProviderType.GROQ,
                    base_url="https://api.groq.com/openai/v1",
                    default_model="llama-3.3-70b-versatile",
                    models=[
                        "llama-3.3-70b-versatile",
                        "llama-3.1-8b-instant",
                        "llama-3.2-1b-preview",
                        "llama-3.2-3b-preview",
                        "mixtral-8x7b-32768",
                        "gemma2-9b-it",
                    ],
                ),
                "cerebras": ProviderConfig(
                    provider_type=ProviderType.CEREBRAS,
                    base_url="https://api.cerebras.ai/v1",
                    default_model="llama-3.3-70b",
                    models=[
                        "llama-3.3-70b",
                        "llama-3.1-8b",
                        "llama-3.1-70b",
                    ],
                ),
                "cohere": ProviderConfig(
                    provider_type=ProviderType.COHERE,
                    base_url="https://api.cohere.ai/v2",
                    default_model="command-r-plus",
                    models=[
                        "command-r-plus",
                        "command-r",
                        "command",
                        "command-light",
                    ],
                ),
                "deepinfra": ProviderConfig(
                    provider_type=ProviderType.DEEPINFRA,
                    base_url="https://api.deepinfra.com/v1/openai",
                    default_model="meta-llama/Llama-3.3-70B-Instruct",
                    models=[
                        "meta-llama/Llama-3.3-70B-Instruct",
                        "meta-llama/Llama-3.1-8B-Instruct",
                        "meta-llama/Llama-3.1-70B-Instruct",
                        "mistralai/Mistral-Small-24B-Instruct-2501",
                    ],
                ),
                "togetherai": ProviderConfig(
                    provider_type=ProviderType.TOGETHERAI,
                    base_url="https://api.together.xyz/v1",
                    default_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
                    models=[
                        "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                        "meta-llama/Llama-3.1-8B-Instruct-Turbo",
                        "mistralai/Mistral-7B-Instruct-v0.3",
                        "Qwen/Qwen2.5-72B-Instruct-Turbo",
                    ],
                ),
                "perplexity": ProviderConfig(
                    provider_type=ProviderType.PERPLEXITY,
                    base_url="https://api.perplexity.ai",
                    default_model="llama-3.1-sonar-large-128k-online",
                    models=[
                        "llama-3.1-sonar-large-128k-online",
                        "llama-3.1-sonar-small-128k-online",
                        "llama-3.1-sonar-large-128k-chat",
                        "llama-3.1-sonar-small-128k-chat",
                    ],
                ),
                "openrouter": ProviderConfig(
                    provider_type=ProviderType.OPENROUTER,
                    base_url="https://openrouter.ai/api/v1",
                    default_model="anthropic/claude-3.5-sonnet",
                    models=[
                        "anthropic/claude-3.5-sonnet",
                        "anthropic/claude-3-opus",
                        "openai/gpt-4o",
                        "openai/gpt-4-turbo",
                        "google/gemini-pro",
                        "meta-llama/llama-3.1-70b-instruct",
                    ],
                ),
                "github_copilot": ProviderConfig(
                    provider_type=ProviderType.GITHUB_COPILOT,
                    base_url="https://api.githubcopilot.com",
                    default_model="gpt-4o",
                    models=[
                        "gpt-4o",
                        "gpt-4o-mini",
                        "gpt-4-turbo",
                        "o1-preview",
                        "o1-mini",
                    ],
                ),
                "opencode": ProviderConfig(
                    provider_type=ProviderType.OPENCODE,
                    base_url="https://opencode.ai/zen/v1",
                    default_model="big-pickle",
                    models=[
                        "big-pickle",
                        "mimo-v2-flash-free",
                        "minimax-m2.1-free",
                        "mimo-v2-omni-free",
                        "qwen3.6-plus-free",
                        "grok-code",
                        "kimi-k2.5-free",
                        "glm-5-free",
                        "gpt-5-nano",
                        "nemotron-3-super-free",
                        "minimax-m2.5-free",
                        "trinity-large-preview-free",
                        "glm-4.7-free",
                        "mimo-v2-pro-free",
                    ],
                ),
                "local_builtin": ProviderConfig(
                    provider_type=ProviderType.LOCAL_BUILTIN,
                    base_url="",
                    default_model="qwen3:0.6b",
                    models=cls._get_local_builtin_models(),
                    is_local=True,
                ),
            },
            active_provider="ollama",
        )


@dataclass
class CodingPlan:
    """Coding plan configuration for opencode-style plans."""

    name: str
    description: str
    enabled: bool = True
    max_iterations: int = 50
    auto_approve: bool = False
    tools: list[str] = field(default_factory=list)


@dataclass
class PlanConfig:
    """Configuration for coding plans."""

    plans: dict[str, CodingPlan] = field(default_factory=dict)
    active_plan: str = "default"

    @classmethod
    def defaults(cls) -> PlanConfig:
        return cls(
            plans={
                "default": CodingPlan(
                    name="default",
                    description="Standard coding assistant mode",
                    max_iterations=50,
                    tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep", "Agent"],
                ),
                "quick": CodingPlan(
                    name="quick",
                    description="Quick mode with auto-approve for fast iterations",
                    max_iterations=20,
                    auto_approve=True,
                    tools=["Read", "Write", "Edit", "Bash"],
                ),
                "explorer": CodingPlan(
                    name="explorer",
                    description="Read-only exploration mode",
                    max_iterations=30,
                    tools=["Read", "Glob", "Grep", "Bash"],
                ),
                "architect": CodingPlan(
                    name="architect",
                    description="Architecture planning mode",
                    max_iterations=100,
                    tools=["Read", "Glob", "Grep", "Agent"],
                ),
            },
            active_plan="default",
        )

    def get_active_plan(self) -> CodingPlan:
        return self.plans.get(self.active_plan, self.plans["default"])
