import os
import httpx
import logging
from typing import Any, Optional, Dict
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from tools.llm_client_base import BaseLLMClient

logger = logging.getLogger(__name__)

class GroqResponse:
    """Mock response object to match GeminiClient/DeepSeekClient interface."""
    def __init__(self, text: str):
        self.text = text

class GroqClient(BaseLLMClient):
    """
    Groq API client with OpenAI compatibility.
    Provides extreme low-latency async content generation for the legal classifier.
    """

    def __init__(self, model_name: str = "llama-3.1-8b-instant", api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY must be set in environment.")
        
        self.model_name = model_name
        self.base_url = "https://api.groq.com/openai/v1"
        self.timeout = httpx.Timeout(10.0, connect=5.0) # Lower timeout for Groq speed

    @retry(
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError)),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def generate_content_async(self, prompt: str, **kwargs: Any) -> Any:
        """
        Generates content using Groq Chat Completions API.
        Returns a GroqResponse object with a .text attribute.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Merge system prompt if provided in kwargs or use default
        system_content = kwargs.get("system_instruction", "Bạn là một chuyên gia pháp luật Việt Nam.")
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt}
            ],
            "temperature": kwargs.get("temperature", 0.0),
            "stream": False
        }

        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            response = await client.post("/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            return GroqResponse(text=content)
