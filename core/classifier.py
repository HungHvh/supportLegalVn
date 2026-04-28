import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from tools.gemini_client import GeminiClient

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

    def __init__(self, model_name: str = "gemini-2.0-flash", api_key: Optional[str] = None):
        self.client = GeminiClient(model_name=model_name, api_key=api_key)

    async def classify(self, query: str) -> QueryClassification:
        """
        Classifies the user query using centralized GeminiClient.
        """
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
        
        try:
            response = await self.client.generate_content_async(full_prompt)
            content = response.text.strip()
            
            # Clean markdown if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            data = json.loads(content)
            result = QueryClassification(**data)
        except Exception as e:
            print(f"Classifier error (after retries): {e}. Falling back to General.")
            result = QueryClassification(domains=["General"], confidence=0.0, is_explicit_filter=False)
            
        return result

    def _format_domains(self) -> str:
        return "\n".join([f"- {k}: {v}" for k, v in self.DOMAINS.items()])
