import os
from dataclasses import dataclass
from typing import Any, Dict
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from tools.llm_client_base import BaseLLMClient
@dataclass
class ProviderResponse:
    text: str
class QwenOllamaClient(BaseLLMClient):
    """Ollama chat client for local Qwen fallback."""
    def __init__(self, model_name: str = "qwen-14b-chat"):
        self.model_name = model_name
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        self.timeout_seconds = float(os.getenv("CLASSIFIER_PROVIDER_TIMEOUT", "20"))
    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError)),
        wait=wait_exponential(multiplier=1, min=1, max=6),
        stop=stop_after_attempt(2),
        reraise=True,
    )
    async def generate_content_async(self, prompt: str, **kwargs: Any) -> ProviderResponse:
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": kwargs.get("temperature", 0.1)},
        }
        url = f"{self.base_url}/api/chat"
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        content = data.get("message", {}).get("content", "")
        return ProviderResponse(text=str(content).strip())
