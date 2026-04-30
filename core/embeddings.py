import asyncio
import logging
import os
from abc import ABC, abstractmethod
from typing import List, Dict
import torch

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

SAFE_EMBEDDING_MODEL_NAME = "bkai-foundation-models/vietnamese-bi-encoder"

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
    def __init__(self, model_name: str = None):
        requested_model = model_name or os.getenv("EMBEDDING_MODEL_NAME", SAFE_EMBEDDING_MODEL_NAME)
        self.model_name = requested_model
        
        # Auto-detect device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device} for embedding model")

        try:
            self.model = SentenceTransformer(requested_model, device=device)
        except Exception as exc:
            if requested_model == SAFE_EMBEDDING_MODEL_NAME:
                raise

            logger.warning(
                "Failed to load embedding model '%s' (%s). Falling back to '%s'.",
                requested_model,
                exc,
                SAFE_EMBEDDING_MODEL_NAME,
            )
            self.model_name = SAFE_EMBEDDING_MODEL_NAME
            self.model = SentenceTransformer(SAFE_EMBEDDING_MODEL_NAME, device=device)

    @property
    def dimension(self) -> int:
        return self.model.get_embedding_dimension()

    async def get_embedding(self, text: str) -> List[float]:
        embedding = self.model.encode(text)
        return embedding.tolist()

    async def batch_get_embeddings(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts, batch_size=64, show_progress_bar=False)
        return embeddings.tolist()

from fastembed import SparseTextEmbedding

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
        # self.sparse = SparseEmbeddingProvider()

    async def get_hybrid_embeddings(self, texts: List[str]) -> List[Dict]:
        dense_vecs = await self.dense.batch_get_embeddings(texts)
        # sparse_task = self.sparse.batch_get_sparse_embeddings(texts)

        # dense_vecs, sparse_vecs = await asyncio.gather(
        #     dense_task,
        #     sparse_task
        # )

        print("texts:", len(texts))
        print("dense_vecs:", len(dense_vecs))

        return [
            {"dense": d, "sparse": []}
            for d in dense_vecs
        ]
