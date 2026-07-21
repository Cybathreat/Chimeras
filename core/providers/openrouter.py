"""
Chimeras v2.0 — OpenRouter Provider
Any model via OpenRouter API (anthropic/claude-3.5-sonnet, openai/gpt-4o, etc.)
"""

from typing import Optional, AsyncIterator

from core.llm_router import LLMProvider


class OpenRouterProvider(LLMProvider):
    """OpenRouter API provider for multi-model access."""
    
    def __init__(self, model: str = "anthropic/claude-3.5-sonnet", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self._client = None
    
    def _get_client(self):
        """Lazy-load OpenRouter client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url="https://openrouter.ai/api/v1"
                )
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._client
    
    async def stream(self, prompt: str, system: Optional[str] = None,
                     max_tokens: int = 4096, **kwargs) -> AsyncIterator[str]:
        """Stream OpenRouter response token by token."""
        client = self._get_client()
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        stream = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def generate(self, prompt: str, system: Optional[str] = None,
                 max_tokens: int = 4096, **kwargs) -> str:
        """Generate complete OpenRouter response."""
        client = self._get_client()
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
