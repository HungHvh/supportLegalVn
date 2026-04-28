import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from tools.gemini_client import GeminiClient
from tools.qwen_dashscope_client import QwenDashScopeClient
from tools.qwen_ollama_client import QwenOllamaClient

class QueryClassification(BaseModel):
    """Schema for legal query classification results."""
    domains: List[str] = Field(description="List of legal domains relevant to the query")
    confidence: float = Field(description="Confidence score for the classification (0.0 to 1.0)")
    is_explicit_filter: bool = Field(description="True if user explicitly requested a specific law or document")

class LegalQueryClassifier:
    """Classifies legal queries into specific Vietnamese legal domains."""

    DOMAINS = {
        "Civil & Family": "Dân sự, Hôn nhân, Gia đình, Thừa kế, Hợp đồng dân sự",
        "Criminal": "Hình sự, Tội phạm, Khung hình phạt, Tố tụng hình sự",
        "Business & Commercial": "Doanh nghiệp, Thương mại, Thành lập công ty, Phá sản, Sở hữu trí tuệ",
        "Labor & Insurance": "Lao động, Bảo hiểm xã hội, Bảo hiểm y tế, Hợp đồng lao động",
        "Administrative & Tax": "Hành chính, Thuế, Xử phạt giao thông, Thủ tục hành chính",
        "Land & Real Estate": "Đất đai, Bất động sản, Sổ đỏ, Tranh chấp đất đai"
    }

    def __init__(
        self,
        provider: str = "dashscope",
        fallback_provider: str = "ollama",
        model_name: str = "qwen-14b-chat",
        api_key: Optional[str] = None,
    ):
        self.provider = provider.lower()
        self.fallback_provider = fallback_provider.lower()
        self.model_name = model_name
        self.api_key = api_key
        self._clients: Dict[str, Any] = {}

    async def classify(self, query: str) -> QueryClassification:
        """Classifies a user query with provider failover and safe fallback."""
        system_prompt = f"""Bạn là một chuyên gia pháp luật Việt Nam. 
Nhiệm vụ của bạn là phân loại câu hỏi của người dùng vào các lĩnh vực luật tương ứng.
Dưới đây là các lĩnh vực và mô tả:
{self._format_domains()}

Hãy trả về kết quả dưới định dạng JSON với các trường:
- domains: Danh sách các lĩnh vực (ví dụ: ["Criminal", "Business & Commercial"]). Nếu không chắc chắn hoặc câu hỏi quá chung chung, hãy trả về ["General"].
- confidence: Độ tin cậy (0.0 đến 1.0).
- is_explicit_filter: True nếu người dùng nhắc đến đích danh một văn bản luật (ví dụ: 'Theo Luật Đất đai 2024...').

Hãy chỉ trả về kết quả dưới định dạng JSON nguyên bản, không kèm theo markdown block hay giải thích gì thêm.
"""

        full_prompt = f"{system_prompt}\n\nCâu hỏi: {query}"

        # Try primary provider first, then fallback provider.
        for provider_name in [self.provider, self.fallback_provider]:
            if not provider_name:
                continue
            try:
                response = await self._call_provider(provider_name, full_prompt)
                content = getattr(response, "text", "").strip()
                data = self._parse_json_response(content)
                return QueryClassification(**data)
            except Exception as e:
                print(f"Classifier provider '{provider_name}' failed: {e}")

        return QueryClassification(domains=["General"], confidence=0.0, is_explicit_filter=False)

    async def _call_provider(self, provider_name: str, prompt: str) -> Any:
        client = self._get_client(provider_name)
        return await client.generate_content_async(prompt)

    def _get_client(self, provider_name: str) -> Any:
        if provider_name in self._clients:
            return self._clients[provider_name]

        provider_name = provider_name.lower()
        if provider_name == "gemini":
            model_name = self.model_name if self.model_name.startswith("gemini") else "gemini-2.0-flash"
            client = GeminiClient(model_name=model_name, api_key=self.api_key)
        elif provider_name == "dashscope":
            client = QwenDashScopeClient(model_name=self.model_name, api_key=self.api_key)
        elif provider_name == "ollama":
            client = QwenOllamaClient(model_name=self.model_name)
        else:
            raise ValueError(f"Unsupported classifier provider: {provider_name}")

        self._clients[provider_name] = client
        return client

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        try:
            # Clean markdown if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            return json.loads(content)
        except Exception as e:
            raise ValueError(f"Invalid classifier JSON response: {e}") from e

    def _format_domains(self) -> str:
        return "\n".join([f"- {k}: {v}" for k, v in self.DOMAINS.items()])
