"""
Chimeras v2.0 — Google Provider
Gemini 2.5 Flash and Pro models via Google AI API.
"""

from typing import Optional, AsyncIterator

from core.llm_router import LLMProvider


class GoogleProvider(LLMProvider):
    """Google Gemini API provider."""
    
    def __init__(self, model: str = "gemini-2.5-flash", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self._client = None
    
    def _get_client(self):
        """Lazy-load Google client."""
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                raise ImportError("google-genai package required: pip install google-genai")
        return self._client
    
    async def stream(self, prompt: str, system: Optional[str] = None,
                     **kwargs) -> AsyncIterator[str]:
        """Stream Gemini response token by token."""
        client = self._get_client()
        
        full_prompt = prompt
        if system:
            full_prompt = f"System: {system}\n\n{prompt}"
        
        response = client.models.generate_content_stream(
            model=self.model,
            contents=full_prompt
        )
        
        for chunk in response:
            if chunk.text:
                yield chunk.text
    
    def generate(self, prompt: str, system: Optional[str] = None,
                 **kwargs) -> str:
        """Generate complete Gemini response."""
        client = self._get_client()
        
        full_prompt = prompt
        if system:
            full_prompt = f"System: {system}\n\n{prompt}"
        
        response = client.models.generate_content(
            model=self.model,
            contents=full_prompt
        )
        return response.text
