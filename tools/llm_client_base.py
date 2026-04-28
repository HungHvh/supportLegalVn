from abc import ABC, abstractmethod
from typing import Any


class BaseLLMClient(ABC):
    """Minimal async contract for classifier LLM providers."""

    @abstractmethod
    async def generate_content_async(self, prompt: str, **kwargs: Any) -> Any:
        raise NotImplementedError

