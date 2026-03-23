"""
SwarmBots v2.0 — Ollama Provider

Local Ollama models (DEFAULT provider). qwen2.5, llama3, etc.
"""

from typing import Optional, AsyncIterator
import httpx

from core.llm_router import LLMProvider


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""
    
    def __init__(self, model: str = "qwen2.5:14b", api_key: Optional[str] = None):
        self.model = model
        self.api_key = None  # Ollama doesn't need API key
        self.base_url = "http://localhost:11434"
    
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
        
        async with httpx.AsyncClient() as client:
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
            "stream": False
        }
        if system:
            payload["system"] = system
        
        response = httpx.post(f"{self.base_url}/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")
