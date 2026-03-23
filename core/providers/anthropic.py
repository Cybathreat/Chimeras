"""
SwarmBots v2.0 — Anthropic Provider

Claude Opus, Sonnet, and Haiku models via Anthropic API.
"""

from typing import Optional, AsyncIterator
import asyncio

from core.llm_router import LLMProvider


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""
    
    def __init__(self, model: str = "claude-opus-4-6-20250929", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self._client = None
    
    def _get_client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package required: pip install anthropic")
        return self._client
    
    async def stream(self, prompt: str, system: Optional[str] = None, 
                     max_tokens: int = 4096, **kwargs) -> AsyncIterator[str]:
        """Stream Claude response token by token."""
        client = self._get_client()
        
        async with client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system or "You are a cybersecurity assistant.",
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            async for text in stream.text_stream:
                yield text
    
    def generate(self, prompt: str, system: Optional[str] = None,
                 max_tokens: int = 4096, **kwargs) -> str:
        """Generate complete Claude response."""
        client = self._get_client()
        
        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system or "You are a cybersecurity assistant.",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
