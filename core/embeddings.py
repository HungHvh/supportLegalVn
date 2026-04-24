from abc import ABC, abstractmethod
from typing import List
from sentence_transformers import SentenceTransformer

class EmbeddingProvider(ABC):
    """
    Interface cho các dịch vụ tạo Vector Embedding.
    Hỗ trợ cả chạy Local hoặc gọi API (OpenAI, Gemini, v.v.)
    """
    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        pass

    @abstractmethod
    async def batch_get_embeddings(self, texts: List[str]) -> List[List[float]]:
        pass

class VietnameseSBERTProvider(EmbeddingProvider):
    """
    Sử dụng model keepitreal/vietnamese-sbert chạy local.
    """
    def __init__(self, model_name: str = "keepitreal/vietnamese-sbert"):
        self.model = SentenceTransformer(model_name)

    async def get_embedding(self, text: str) -> List[float]:
        # Vì model chạy local trên CPU/GPU, ta dùng encode đồng bộ nhưng bọc trong async
        # để tuân thủ interface và tránh block FastAPI event loop nếu cần.
        embedding = self.model.encode(text)
        return embedding.tolist()

    async def batch_get_embeddings(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts)
        return embeddings.tolist()
