import os
import asyncio
import aiosqlite
from typing import List, Dict, Any, Optional, AsyncGenerator
from llama_index.core.retrievers import BaseRetriever
from llama_index.core import QueryBundle
from llama_index.core.schema import NodeWithScore, TextNode
from sentence_transformers import CrossEncoder

from core.classifier import LegalQueryClassifier
from retrievers.sqlite_retriever import SQLiteFTS5Retriever
from retrievers.qdrant_retriever import QdrantRetriever
from tools.gemini_client import GeminiClient
from tools.groq_client import GroqClient
from tools.deepseek_client import DeepSeekClient
from tools.qwen_dashscope_client import QwenDashScopeClient
import torch


def _accumulate_rrf(results, fused_scores: Dict[str, float], chunk_data: Dict[str, Any], rrf_k: int) -> None:
    for rank, res in enumerate(results):
        node = res.node
        cid = node.node_id

        fused_scores[cid] = fused_scores.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)
        chunk_data.setdefault(
            cid,
            {
                "content": node.text,
                "article_uuid": node.metadata.get("article_uuid"),
            },
        )


def _build_context_str(nodes: List[NodeWithScore]) -> str:
    return "\n\n".join(
        f"Văn bản: {n.node.metadata.get('so_ky_hieu')} - {n.node.metadata.get('article_title')}\n"
        f"Nội dung:\n{n.node.get_content()}"
        for n in nodes
    )

class LegalHybridRetriever(BaseRetriever):
    """
    Phase 10 Hybrid retriever:
    1. Vector (Qdrant) + Keyword (SQLite FTS5) at chunk level
    2. RRF fusion (chunk-level)
    3. Rerank top-30 chunks (BAAI/bge-reranker-v2-m3)
    4. Group by article_uuid -> top-5 articles
    5. Expand siblings for context
    """

    def __init__(
        self, 
        classifier: LegalQueryClassifier,
        vector_retriever: QdrantRetriever,
        fts_retriever: SQLiteFTS5Retriever,
        db_path: str = "legal_poc.db",
        rrf_k: int = 60,
        top_k: int = 5, # Final number of articles
        rerank_top_n: int = 10,
        rerank_input_size: int = 30,
        use_classifier: bool = True
    ):
        self.classifier = classifier
        self.vector_retriever = vector_retriever
        self.fts_retriever = fts_retriever
        self.db_path = db_path
        self.rrf_k = rrf_k
        self.top_k = top_k
        self.rerank_top_n = rerank_top_n
        self.rerank_input_size = rerank_input_size
        self.use_classifier = use_classifier
        
        # Load reranker once
        reranker_model = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._reranker = CrossEncoder(reranker_model, device=device)
            print(f"[OK] Reranker loaded: {reranker_model} on {device}")
        except Exception as e:
            print(f"[Warning] Failed to load reranker: {e}. Reranking will be skipped.")
            self._reranker = None
            
        super().__init__()

    async def _aretrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Phase 10: 11-step pipeline."""
        query_str = query_bundle.query_str
        
        # 1. Classify (Optional)
        domains = []
        if self.use_classifier:
            try:
                classification = await self.classifier.classify(query_str)
                domains = classification.domains
            except Exception:
                pass
        
        # 2-4. Search & RRF (chunk-level)
        tasks = [
            self.vector_retriever.aretrieve_with_filter(query_bundle, domains=domains),
            self.fts_retriever.aretrieve(query_bundle)
        ]
        vector_nodes, fts_nodes = await asyncio.gather(*tasks)

        fused_scores: Dict[str, float] = {}
        chunk_data: Dict[str, Any] = {}

        _accumulate_rrf(vector_nodes, fused_scores, chunk_data, self.rrf_k)
        _accumulate_rrf(fts_nodes, fused_scores, chunk_data, self.rrf_k)

        # 5. Top-30 chunks for reranking
        top_chunk_ids = [
            cid
            for cid, _ in sorted(
                fused_scores.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:self.rerank_input_size]
        ]
        
        if not top_chunk_ids:
            return []

        # 6. Ensure we have content for all top chunks (fetch from SQLite if missing from Qdrant payload)
        # In indexer.py, we stored content in payload, so it should be there.
        # But let's verify or fetch from legal_chunks if needed.
        missing_ids = [
            cid
            for cid in top_chunk_ids
            if cid not in chunk_data or not chunk_data[cid]["content"]
        ]
        if missing_ids:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                placeholders = ",".join("?" * len(missing_ids))
                async with db.execute(f"SELECT chunk_id, content, article_uuid FROM legal_chunks WHERE chunk_id IN ({placeholders})", missing_ids) as cursor:
                    rows = await cursor.fetchall()
                    for row in rows:
                        chunk_data[row["chunk_id"]] = {
                            "content": row["content"],
                            "article_uuid": row["article_uuid"]
                        }

        # 7. Rerank (Cross-Encoder)
        final_chunks = []
        if self._reranker and top_chunk_ids:
            valid_chunks = [
                (cid, chunk_data[cid]["content"])
                for cid in top_chunk_ids
                if cid in chunk_data and chunk_data[cid]["content"]
            ]
            if not valid_chunks:
                return []

            pairs = [(query_str, content) for _, content in valid_chunks]
            scores = self._reranker.predict(pairs)
            ranked = sorted(zip(valid_chunks, scores), key=lambda x: -x[1])
            final_chunks = [
                (cid, float(score))
                for ((cid, _), score) in ranked[:self.rerank_top_n]
            ]
        else:
            final_chunks = [(cid, float(fused_scores[cid])) for cid in top_chunk_ids if cid in fused_scores]

        # 8. Group by article_uuid -> top-5 articles
        article_scores: Dict[str, float] = {}
        article_best_chunk: Dict[str, str] = {} # Keep track of best chunk for metadata
        
        for cid, score in final_chunks:
            data = chunk_data.get(cid)
            if not data:
                continue

            uuid = data["article_uuid"]
            prev = article_scores.get(uuid)
            if prev is None or score > prev:
                article_scores[uuid] = float(score)
                article_best_chunk[uuid] = cid

        top_article_uuids = sorted(article_scores, key=article_scores.get, reverse=True)[:self.top_k]

        # 9-10. Expand siblings & Fetch full articles
        if not top_article_uuids:
            return []

        results = []
        placeholders = ",".join("?" * len(top_article_uuids))
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"""
                SELECT article_uuid, so_ky_hieu, article_title, full_content
                FROM legal_articles
                WHERE article_uuid IN ({placeholders})
                """,
                top_article_uuids,
            ) as cursor:
                rows = await cursor.fetchall()

        article_map = {row["article_uuid"]: row for row in rows}

        for uuid in top_article_uuids:
            article = article_map.get(uuid)
            if not article:
                continue

            metadata = {
                "article_uuid": article["article_uuid"],
                "so_ky_hieu": article["so_ky_hieu"],
                "article_title": article["article_title"],
                "type": "ARTICLE"
            }

            node = TextNode(
                text=article["full_content"],
                id_=article["article_uuid"],
                metadata=metadata
            )
            results.append(NodeWithScore(node=node, score=article_scores[uuid]))

        return results

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        return asyncio.run(self._aretrieve(query_bundle))

class LegalRAGPipeline:
    """
    Phase 10 RAG Pipeline: Returns full articles with citations.
    """
    def __init__(
        self, 
        retriever: LegalHybridRetriever, 
        provider: str = "gemini",
        model_name: Optional[str] = None,
        llm: Optional[Any] = None
    ):
        self.retriever = retriever
        if llm:
            self.client = llm
        else:
            self.client = self._get_client(provider, model_name)
        
        self.qa_prompt_template = (
            "Bạn là một chuyên gia pháp luật Việt Nam cao cấp. "
            "Hãy trả lời câu hỏi của người dùng dựa trên các tài liệu pháp luật (các Điều luật) được cung cấp dưới đây.\n"
            "---------------------\n"
            "{context_str}\n"
            "---------------------\n"
            "Yêu cầu về cấu trúc câu trả lời (IRAC):\n"
            "1. Vấn đề (Issue): Tóm tắt ngắn gọn vấn đề pháp lý của người dùng.\n"
            "2. Quy định (Rule): Trích dẫn chính xác các Điều, Khoản từ các văn bản pháp luật liên quan. "
            "Sử dụng định dạng: 'Theo [Khoản], [Điều], [Tên văn bản]...'.\n"
            "3. Phân tích (Analysis): Giải thích cách các quy định trên áp dụng vào trường hợp cụ thể của người dùng.\n"
            "4. Kết luận (Conclusion): Đưa ra lời khuyên hoặc hướng giải quyết cuối cùng.\n\n"
            "Lưu ý quan trọng:\n"
            "- Nếu thông tin không có trong tài liệu, hãy nói rõ 'Tôi không tìm thấy quy định cụ thể cho vấn đề này trong cơ sở dữ liệu'.\n"
            "- Tuyệt đối không được bịa đặt (hallucinate) số hiệu văn bản hoặc nội dung luật.\n"
            "- Luôn đi kèm lời nhắc: 'Thông tin này chỉ mang tính chất tham khảo, không thay thế cho tư vấn pháp lý chuyên nghiệp'.\n\n"
            "Câu hỏi: {query_str}\n"
            "Trả lời:"
        )

    def _get_client(self, provider: str, model_name: Optional[str]) -> Any:
        provider = provider.lower()
        if provider == "gemini":
            return GeminiClient(model_name=model_name or "gemini-2.0-flash")
        elif provider == "groq":
            return GroqClient(model_name=model_name or "llama-3.1-70b")
        elif provider == "deepseek":
            return DeepSeekClient(model_name=model_name or "deepseek-chat")
        elif provider == "dashscope":
            return QwenDashScopeClient(model_name=model_name or "qwen-plus")
        else:
            raise ValueError(f"Unsupported generation provider: {provider}")

    async def acustom_query(self, query_str: str) -> Dict[str, Any]:
        """Execute the full RAG pipeline."""
        nodes = await self.retriever.aretrieve(query_str)
        
        context_str = _build_context_str(nodes)
        
        prompt = self.qa_prompt_template.format(
            context_str=context_str, 
            query_str=query_str
        )
        
        response = await self.client.generate_content_async(prompt)
        
        citations = []
        for n in nodes:
            citations.append({
                "source": f"{n.node.metadata.get('so_ky_hieu')} - {n.node.metadata.get('article_title')}",
                "text": n.node.get_content()[:300] + "...",
                "score": float(n.score)
            })
            
        return {
            "answer": response.text,
            "citations": citations,
            "detected_domains": [],
            "confidence_score": 0.0
        }

    async def astream_query(self, query_str: str) -> AsyncGenerator[str, None]:
        """Stream the RAG response."""
        nodes = await self.retriever.aretrieve(query_str)
        
        context_str = _build_context_str(nodes)
        
        prompt = self.qa_prompt_template.format(
            context_str=context_str, 
            query_str=query_str
        )
        
        async for chunk in self.client.astream_query(prompt):
            if chunk.text:
                yield chunk.text
