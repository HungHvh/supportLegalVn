import os
import asyncio
import logging
from typing import Any, Optional, AsyncGenerator, List, Dict
import google.generativeai as genai
from google.api_core import exceptions
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

logger = logging.getLogger(__name__)

class GeminiClient:
    """
    Centralized Gemini client with robust retry logic and error handling.
    Wraps Google Native SDK calls.
    """
    
    def __init__(self, model_name: str = "gemini-2.0-flash", api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be set in environment.")
        
        genai.configure(api_key=self.api_key)
        self.model_name = model_name
        self.model = genai.GenerativeModel(model_name)

    @retry(
        retry=retry_if_exception_type((exceptions.ResourceExhausted, exceptions.InternalServerError, exceptions.ServiceUnavailable)),
        wait=wait_exponential(multiplier=2, min=45, max=120),
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def generate_content_async(self, prompt: str, **kwargs) -> Any:
        """
        Generates content with automatic retries on rate limits or server errors.
        """
        try:
            return await self.model.generate_content_async(prompt, **kwargs)
        except exceptions.ResourceExhausted as e:
            # Re-raise to trigger tenacity retry
            logger.warning(f"Quota exceeded for {self.model_name}. Retrying...")
            raise e
        except Exception as e:
            logger.error(f"Unexpected Gemini error: {e}")
            raise e

    async def astream_query(self, prompt: str, **kwargs) -> AsyncGenerator[Any, None]:
        """
        Streams content with basic error handling. 
        Note: Retrying streams is complex; for now, we just handle the exception.
        """
        try:
            response = await self.model.generate_content_async(prompt, stream=True, **kwargs)
            async for chunk in response:
                yield chunk
        except exceptions.ResourceExhausted:
            logger.error("Quota exceeded during streaming.")
            raise
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise
