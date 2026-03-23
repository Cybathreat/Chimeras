"""
SwarmBots v2.0 — Universal LLM Router

Routes LLM requests to any of 6 providers with a unified interface.
Fallback chain: groq → openrouter → ollama
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
    """
    
    def __init__(self, provider_name: str = "ollama", model: Optional[str] = None, api_key: Optional[str] = None):
        self.provider_name = provider_name.lower()
        self.model = model or self._get_default_model(provider_name)
        self.api_key = api_key or self._get_api_key(provider_name)
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
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY",
            "groq": "GROQ_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "openai": "OPENAI_API_KEY",
            "ollama": None  # Ollama doesn't need API key
        }
        env_var = env_keys.get(provider)
        return os.environ.get(env_var) if env_var else None
    
    def _load_provider(self) -> LLMProvider:
        """Dynamically load the provider implementation."""
        if self._provider:
            return self._provider
        
        provider_map = {
            "anthropic": "providers.anthropic.AnthropicProvider",
            "google": "providers.google.GoogleProvider",
            "groq": "providers.groq.GroqProvider",
            "openrouter": "providers.openrouter.OpenRouterProvider",
            "openai": "providers.openai.OpenAIProvider",
            "ollama": "providers.ollama.OllamaProvider"
        }
        
        module_path = provider_map.get(self.provider_name)
        if not module_path:
            raise ValueError(f"Unknown provider: {self.provider_name}")
        
        module_name, class_name = module_path.rsplit(".", 1)
        module = __import__(module_name, fromlist=[class_name])
        provider_class = getattr(module, class_name)
        self._provider = provider_class(model=self.model, api_key=self.api_key)
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
                "warchief": {"provider": "anthropic", "model": "claude-opus-4-6"},
                "aria": {"provider": "ollama", "model": "qwen2.5:14b"},
                ...
            }
        }
        """
        bot_config = swarm_config.get("bots", {}).get(bot_name, {})
        provider = bot_config.get("provider", "ollama")
        model = bot_config.get("model")
        return cls(provider_name=provider, model=model)
