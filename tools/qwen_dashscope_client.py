import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from tools.llm_client_base import BaseLLMClient
@dataclass
class ProviderResponse:
    text: str
class QwenDashScopeClient(BaseLLMClient):
    """DashScope-compatible chat client for Qwen models."""
    def __init__(self, model_name: str = "qwen-14b-chat", api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY must be set for DashScope classifier provider.")
        self.model_name = model_name
        self.base_url = os.getenv(
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        )
        self.timeout_seconds = float(os.getenv("CLASSIFIER_PROVIDER_TIMEOUT", "20"))
    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def generate_content_async(self, prompt: str, **kwargs: Any) -> ProviderResponse:
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.1),
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return ProviderResponse(text=str(content).strip())
