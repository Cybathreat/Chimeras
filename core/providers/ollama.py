"""
Chimeras v2.0 — Ollama Provider
Local Ollama models (DEFAULT provider). qwen2.5, llama3, etc.
Supports custom base_url for remote Ollama instances.
"""

from typing import Optional, AsyncIterator
import httpx

from core.llm_router import LLMProvider


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider.

    Supports both local Ollama (default http://localhost:11434) and
    remote Ollama instances via base_url parameter.
    """

    # Default timeout: 120 seconds (Ollama can be slow with large models)
    DEFAULT_TIMEOUT = 300.0

    def __init__(self, model: str = "qwen2.5:14b", api_key: Optional[str] = None,
                 base_url: Optional[str] = None):
        self.model = model
        self.api_key = None  # Ollama doesn't need API key
        self.base_url = base_url or "http://localhost:11434"

    async def stream(self, prompt: str, system: Optional[str] = None,
                     **kwargs) -> AsyncIterator[str]:
        """Stream Ollama response token by token."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True
        }
        if system:
            payload["system"] = system

        timeout = httpx.Timeout(self.DEFAULT_TIMEOUT, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        import json
                        data = json.loads(line)
                        if "response" in data:
                            yield data["response"]

    def generate(self, prompt: str, system: Optional[str] = None,
                 **kwargs) -> str:
        """Generate complete Ollama response."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 256,
            }
        }
        if system:
            payload["system"] = system

        timeout = httpx.Timeout(self.DEFAULT_TIMEOUT, connect=10.0)
        response = httpx.post(f"{self.base_url}/api/generate", json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")