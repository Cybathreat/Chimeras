"""
Chimeras v2.0 — Universal LLM Router
Routes LLM requests to any of 6 providers with a unified interface.
Fallback chain: groq → openrouter → ollama

Supports custom base_url for OpenAI and Anthropic providers (gateways, proxies).
base_url is resolved from bot config (swarm-config.json) or environment variables:
  OPENAI_BASE_URL, ANTHROPIC_BASE_URL, OPENAI_API_KEY, ANTHROPIC_API_KEY
"""

from typing import Optional, Dict, Any, AsyncIterator
from abc import ABC, abstractmethod
import os


class LLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    @abstractmethod
    async def stream(self, prompt: str, system: Optional[str] = None, **kwargs) -> AsyncIterator[str]:
        """Stream LLM response token by token."""
        pass

    @abstractmethod
    def generate(self, prompt: str, system: Optional[str] = None, **kwargs) -> str:
        """Generate complete LLM response."""
        pass


class LLMRouter:
    """
    Universal LLM router that selects provider based on config.

    Supports: anthropic, google, groq, openrouter, openai, ollama

    base_url support:
      - OpenAI: from config base_url OR env OPENAI_BASE_URL
      - Anthropic: from config base_url OR env ANTHROPIC_BASE_URL
    """

    def __init__(self, provider_name: str = "ollama", model: Optional[str] = None,
                 api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.provider_name = provider_name.lower()
        self.model = model or self._get_default_model(provider_name)
        self.api_key = api_key or self._get_api_key(provider_name)
        self.base_url = base_url or self._get_base_url(provider_name)
        self._provider: Optional[LLMProvider] = None

    def _get_default_model(self, provider: str) -> str:
        """Return default model for each provider."""
        defaults = {
            "anthropic": "claude-opus-4-6-20250929",
            "google": "gemini-2.5-flash",
            "groq": "llama-3.3-70b-versatile",
            "openrouter": "anthropic/claude-3.5-sonnet",
            "openai": "gpt-4o",
            "ollama": "qwen2.5:14b"
        }
        return defaults.get(provider, "qwen2.5:14b")

    def _get_api_key(self, provider: str) -> Optional[str]:
        """Fetch API key from environment."""
        env_keys = {
            "anthropic": ["ANTHROPIC_API_KEY"],
            "google": ["GOOGLE_API_KEY"],
            "groq": ["GROQ_API_KEY"],
            "openrouter": ["OPENROUTER_API_KEY"],
            "openai": ["OPENAI_API_KEY", "OLLAMA_API_KEY"],  # Ollama Cloud is OpenAI-compatible
            "ollama": None
        }
        env_var_list = env_keys.get(provider)
        if not env_var_list:
            return None
        for env_var in env_var_list:
            val = os.environ.get(env_var)
            if val:
                return val
        return None

    def _get_base_url(self, provider: str) -> Optional[str]:
        """Fetch custom base_url from environment for OpenAI/Anthropic."""
        env_base_urls = {
            "openai": "OPENAI_BASE_URL",
            "anthropic": "ANTHROPIC_BASE_URL",
        }
        env_var = env_base_urls.get(provider)
        return os.environ.get(env_var) if env_var else None

    def _load_provider(self) -> LLMProvider:
        """Dynamically load the provider implementation."""
        if self._provider:
            return self._provider

        provider_map = {
            "anthropic": "core.providers.anthropic.AnthropicProvider",
            "google": "core.providers.google.GoogleProvider",
            "groq": "core.providers.groq.GroqProvider",
            "openrouter": "core.providers.openrouter.OpenRouterProvider",
            "openai": "core.providers.openai.OpenAIProvider",
            "ollama": "core.providers.ollama.OllamaProvider"
        }

        module_path = provider_map.get(self.provider_name)
        if not module_path:
            raise ValueError(f"Unknown provider: {self.provider_name}")

        module_name, class_name = module_path.rsplit(".", 1)
        module = __import__(module_name, fromlist=[class_name])
        provider_class = getattr(module, class_name)

        # Build kwargs for provider constructor
        kwargs = {"model": self.model, "api_key": self.api_key}
        # Only pass base_url to providers that support it
        if self.provider_name in ("openai", "anthropic") and self.base_url:
            kwargs["base_url"] = self.base_url

        self._provider = provider_class(**kwargs)
        return self._provider

    async def stream(self, prompt: str, system: Optional[str] = None, **kwargs) -> AsyncIterator[str]:
        """Stream response from configured provider."""
        provider = self._load_provider()
        async for token in provider.stream(prompt, system, **kwargs):
            yield token

    def generate(self, prompt: str, system: Optional[str] = None, **kwargs) -> str:
        """Generate complete response from configured provider."""
        provider = self._load_provider()
        return provider.generate(prompt, system, **kwargs)

    @classmethod
    def from_config(cls, bot_name: str, swarm_config: Dict[str, Any]) -> "LLMRouter":
        """
        Create router instance from swarm-config.json.

        Config format:
        {
            "bots": {
                "warchief": {"provider": "anthropic", "model": "claude-opus-4-6", "base_url": "https://gateway/v1"},
                "aria": {"provider": "ollama", "model": "qwen2.5:14b"},
                ...
            }
        }

        base_url is optional and only used for openai/anthropic providers.
        It can also be set via env vars OPENAI_BASE_URL / ANTHROPIC_BASE_URL.
        """
        bot_config = swarm_config.get("bots", {}).get(bot_name, {})
        provider = bot_config.get("provider", "ollama")
        model = bot_config.get("model")
        base_url = bot_config.get("base_url")  # Optional, from config
        return cls(provider_name=provider, model=model, base_url=base_url)