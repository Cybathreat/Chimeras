"""
Chimeras v1.0 — Groq Provider

Llama 3.3 70B and Mixtral models via Groq API.
"""

from typing import Optional, AsyncIterator

from core.llm_router import LLMProvider


class GroqProvider(LLMProvider):
    """Groq API provider for Llama and Mixtral models."""
    
    def __init__(self, model: str = "llama-3.3-70b-versatile", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self._client = None
    
    def _get_client(self):
        """Lazy-load Groq client."""
        if self._client is None:
            try:
                from groq import AsyncGroq
                self._client = AsyncGroq(api_key=self.api_key)
            except ImportError:
                raise ImportError("groq package required: pip install groq")
        return self._client
    
    async def stream(self, prompt: str, system: Optional[str] = None,
                     max_tokens: int = 4096, **kwargs) -> AsyncIterator[str]:
        """Stream Groq response token by token."""
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
        """Generate complete Groq response."""
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
