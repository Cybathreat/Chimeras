"""
Chimeras v2.0 — OpenAI Provider
GPT-4o and GPT-4 Turbo models via OpenAI API.
Supports custom base_url for OpenAI-compatible gateways (Azure, vLLM, LM Studio, Ollama Cloud, proxies).
"""

from typing import Optional, AsyncIterator

from core.llm_router import LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI GPT API provider.

    Supports both official OpenAI and any OpenAI-compatible endpoint
    (Azure, local gateways, LM Studio, vLLM, Ollama Cloud, etc.) via base_url.
    """

    def __init__(self, model: str = "gpt-4o", api_key: Optional[str] = None,
                 base_url: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self._async_client = None
        self._sync_client = None

    def _get_sync_client(self):
        """Lazy-load sync OpenAI client."""
        if self._sync_client is None:
            try:
                from openai import OpenAI
                kwargs = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._sync_client = OpenAI(**kwargs)
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._sync_client

    def _get_async_client(self):
        """Lazy-load async OpenAI client."""
        if self._async_client is None:
            try:
                from openai import AsyncOpenAI
                kwargs = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._async_client = AsyncOpenAI(**kwargs)
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._async_client

    async def stream(self, prompt: str, system: Optional[str] = None,
                     max_tokens: int = 4096, **kwargs) -> AsyncIterator[str]:
        """Stream GPT response token by token."""
        client = self._get_async_client()

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
        """Generate complete GPT response (sync)."""
        client = self._get_sync_client()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens
        )
        content = response.choices[0].message.content
        # Check if response was truncated
        if hasattr(response, 'usage') and response.usage:
            if response.usage.completion_tokens >= max_tokens - 10:
                content += "\n\n[NOTE: Response may have been truncated due to token limit]"
        return content