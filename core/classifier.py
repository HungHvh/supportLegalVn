import os
from typing import List, Optional
from pydantic import BaseModel, Field
from llama_index.llms.gemini import Gemini
from llama_index.core.llms import ChatMessage

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

    def __init__(self, model_name: str = "models/gemini-1.5-flash", api_key: Optional[str] = None):
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY must be set in environment or passed to constructor.")
        
        self.llm = Gemini(model=model_name, api_key=api_key)

    async def classify(self, query: str) -> QueryClassification:
        """
        Classifies the user query using Gemini.
        Returns 'General' if confidence is low.
        """
        system_prompt = f"""Bạn là một chuyên gia pháp luật Việt Nam. 
Nhiệm vụ của bạn là phân loại câu hỏi của người dùng vào các lĩnh vực luật tương ứng.
Dưới đây là các lĩnh vực và mô tả:
{self._format_domains()}

Hãy trả về kết quả dưới định dạng JSON với các trường:
- domains: Danh sách các lĩnh vực (ví dụ: ["Criminal", "Business & Commercial"]). Nếu không chắc chắn hoặc câu hỏi quá chung chung, hãy trả về ["General"].
- confidence: Độ tin cậy (0.0 đến 1.0).
- is_explicit_filter: True nếu người dùng nhắc đến đích danh một văn bản luật (ví dụ: 'Theo Luật Đất đai 2024...').

Lưu ý: Một câu hỏi có thể thuộc nhiều lĩnh vực.
"""
        
        response = await self.llm.astructured_predict(
            QueryClassification,
            [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=f"Câu hỏi: {query}")
            ]
        )
        
        # Post-processing for low confidence
        if response.confidence < 0.5 and "General" not in response.domains:
            response.domains = ["General"]
            
        return response

    def _format_domains(self) -> str:
        return "\n".join([f"- {k}: {v}" for k, v in self.DOMAINS.items()])

if __name__ == "__main__":
    # Quick test
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    
    async def test():
        classifier = LegalQueryClassifier()
        res = await classifier.classify("Thủ tục ly hôn cần những giấy tờ gì?")
        print(f"Query: Thủ tục ly hôn...")
        print(f"Domains: {res.domains}, Confidence: {res.confidence}")
        
    asyncio.run(test())
