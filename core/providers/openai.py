"""
SwarmBots v2.0 — OpenAI Provider

GPT-4o and GPT-4 Turbo models via OpenAI API.
"""

from typing import Optional, AsyncIterator

from core.llm_router import LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI GPT API provider."""
    
    def __init__(self, model: str = "gpt-4o", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self._client = None
    
    def _get_client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._client
    
    async def stream(self, prompt: str, system: Optional[str] = None,
                     max_tokens: int = 4096, **kwargs) -> AsyncIterator[str]:
        """Stream GPT response token by token."""
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
        """Generate complete GPT response."""
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
