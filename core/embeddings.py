from abc import ABC, abstractmethod
from typing import List, Dict
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
        embedding = self.model.encode(text)
        return embedding.tolist()

    async def batch_get_embeddings(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts)
        return embeddings.tolist()

from fastembed import SparseTextEmbedding, TextEmbedding

class SparseEmbeddingProvider:
    """Sử dụng SPLADE hoặc BM25 từ fastembed để tạo Sparse Vectors."""
    def __init__(self, model_name: str = "prithivida/Splade_PP_en_v1"):
        # Lưu ý: Hiện tại fastembed chưa có model SPLADE chuyên dụng cho tiếng Việt 
        # nhưng BM25/Splade vẫn hoạt động tốt như một túi từ (bag-of-words).
        self.model = SparseTextEmbedding(model_name=model_name)

    async def batch_get_sparse_embeddings(self, texts: List[str]):
        # Trả về iterator của các đối tượng SparseVector (indices, values)
        embeddings = list(self.model.embed(texts))
        return [
            {"indices": e.indices.tolist(), "values": e.values.tolist()}
            for e in embeddings
        ]

class HybridEmbeddingProvider:
    """Kết hợp cả Dense và Sparse Embeddings."""
    def __init__(self, dense_provider: VietnameseSBERTProvider):
        self.dense = dense_provider
        self.sparse = SparseEmbeddingProvider()

    async def get_hybrid_embeddings(self, texts: List[str]) -> List[Dict]:
        dense_vecs = await self.dense.batch_get_embeddings(texts)
        sparse_vecs = await self.sparse.batch_get_sparse_embeddings(texts)
        
        results = []
        for d, s in zip(dense_vecs, sparse_vecs):
            results.append({
                "dense": d,
                "sparse": s
            })
        return results
