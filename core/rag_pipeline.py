import os
import asyncio
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


def _build_context_str(nodes: List[NodeWithScore]) -> str:
    return "\n\n".join(
        f"Văn bản: {n.node.metadata.get('so_ky_hieu')} - {n.node.metadata.get('article_title')}\n"
        f"Nội dung:\n{n.node.get_content()}"
        for n in nodes
    )


def _unique_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


class LegalHybridRetriever(BaseRetriever):
    """
    Article-first retriever for the legal RAG pipeline.

    Flow:
    1. Query article collection in Qdrant.
    2. Expand candidate articles into chunks from SQLite.
    3. Optional rerank at chunk level.
    4. Return top articles as final context nodes.
    """

    def __init__(
        self,
        classifier: Optional[LegalQueryClassifier],
        vector_retriever: QdrantRetriever,
        fts_retriever: SQLiteFTS5Retriever,
        db_path: str = "legal_poc.db",
        top_k: int = 5,
        article_top_k: int = 20,
        chunk_fetch_limit: int = 250,
        rerank_top_n: int = 10,
        rerank_input_size: int = 30,
        use_classifier: bool = True,
        use_fts_fallback: bool = False,
    ):
        self.classifier = classifier
        self.vector_retriever = vector_retriever
        self.fts_retriever = fts_retriever
        self.db_path = db_path
        self.top_k = top_k
        self.article_top_k = article_top_k
        self.chunk_fetch_limit = chunk_fetch_limit
        self.rerank_top_n = rerank_top_n
        self.rerank_input_size = rerank_input_size
        self.use_classifier = use_classifier
        self.use_fts_fallback = use_fts_fallback

        reranker_model = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._reranker = CrossEncoder(reranker_model, device=device)
            print(f"[OK] Reranker loaded: {reranker_model} on {device}")
        except Exception as e:
            print(f"[Warning] Failed to load reranker: {e}. Reranking will be skipped.")
            self._reranker = None

        super().__init__()

    async def _retrieve_article_candidates(
        self,
        query_bundle: QueryBundle,
        query_str: str,
    ) -> List[NodeWithScore]:
        """
        Primary retrieval path: article-level semantic search.
        """
        article_nodes = await self.vector_retriever.aretrieve_articles(
            query_bundle,
            top_k=self.article_top_k,
        )

        if article_nodes:
            return article_nodes

        # Optional fallback: if article collection is empty or not available,
        # use legacy chunk retrieval and map back to article candidates.
        if not self.use_fts_fallback:
            return []

        legacy_chunk_nodes = await asyncio.gather(
            self.vector_retriever.aretrieve_with_filter(query_bundle),
            self.fts_retriever.aretrieve(query_str),
        )

        fused: Dict[str, float] = {}
        article_uuid_to_score: Dict[str, float] = {}

        # Simple RRF-like accumulation on chunks, then group by article_uuid.
        for source_nodes in legacy_chunk_nodes:
            for rank, res in enumerate(source_nodes):
                cid = res.node.node_id
                fused[cid] = fused.get(cid, 0.0) + 1.0 / (60 + rank + 1)
                article_uuid = res.node.metadata.get("article_uuid")
                if article_uuid:
                    article_uuid_to_score[article_uuid] = max(
                        article_uuid_to_score.get(article_uuid, 0.0),
                        fused[cid],
                    )

        if not fused:
            return []

        top_article_uuids = sorted(
            article_uuid_to_score,
            key=article_uuid_to_score.get,
            reverse=True,
        )[: self.top_k]

        if not top_article_uuids:
            return []

        articles = await self.fts_retriever.get_articles_by_uuids(top_article_uuids)
        return articles

    async def _aretrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        query_str = query_bundle.query_str

        # 1. Optional classification (useful for future filtering)
        if self.use_classifier and self.classifier is not None:
            try:
                _classification = await self.classifier.classify(query_str)
                _domains = getattr(_classification, "domains", []) or []
                # Currently not used yet, but kept for future filtering.
            except Exception:
                pass

        # 2. Article-level retrieval
        article_candidates = await self._retrieve_article_candidates(query_bundle, query_str)
        if not article_candidates:
            return []

        article_uuids = _unique_keep_order(
            [n.node.metadata.get("article_uuid") or n.node.node_id for n in article_candidates]
        )

        # 3. Expand candidate articles to chunks from SQLite
        chunk_nodes = await self.fts_retriever.get_chunks_by_articles(
            article_uuids,
            limit=self.chunk_fetch_limit,
        )

        if not chunk_nodes:
            # No chunks found, return articles directly.
            return article_candidates[: self.top_k]

        # 4. Optional rerank on chunks for better article ranking
        scored_chunk_nodes: List[NodeWithScore] = []

        if self._reranker is not None:
            rerank_pool = chunk_nodes[: self.rerank_input_size]
            valid_pairs = [
                (query_str, n.node.get_content())
                for n in rerank_pool
                if n.node.get_content().strip()
            ]

            if valid_pairs:
                scores = self._reranker.predict(valid_pairs)
                for node, score in sorted(zip(rerank_pool, scores), key=lambda x: -x[1]):
                    scored_chunk_nodes.append(
                        NodeWithScore(node=node.node, score=float(score))
                    )
        else:
            scored_chunk_nodes = chunk_nodes[: self.rerank_top_n]

        if not scored_chunk_nodes:
            scored_chunk_nodes = chunk_nodes[: self.rerank_top_n]

        # 5. Aggregate chunk scores back to articles
        article_scores: Dict[str, float] = {}

        for n in scored_chunk_nodes:
            article_uuid = n.node.metadata.get("article_uuid")
            if not article_uuid:
                continue

            score = float(n.score or 0.0)
            if article_uuid not in article_scores or score > article_scores[article_uuid]:
                article_scores[article_uuid] = score

        # If reranker did not produce usable article grouping, fall back to article candidates
        if not article_scores:
            return article_candidates[: self.top_k]

        # 6. Fetch canonical article text from SQLite for final context
        top_article_uuids = sorted(
            article_scores,
            key=article_scores.get,
            reverse=True,
        )[: self.top_k]
        articles = await self.fts_retriever.get_articles_by_uuids(top_article_uuids)

        if not articles:
            return article_candidates[: self.top_k]

        article_map = {n.node.metadata.get("article_uuid"): n for n in articles}
        results: List[NodeWithScore] = []

        for aid in top_article_uuids:
            article_node = article_map.get(aid)
            if article_node is None:
                continue

            # Prefer reranked score if available, otherwise keep semantic article score.
            final_score = article_scores.get(aid, 0.0)
            if final_score <= 0:
                final_score = next(
                    (
                        cand.score
                        for cand in article_candidates
                        if cand.node.metadata.get("article_uuid") == aid
                    ),
                    0.0,
                )

            results.append(
                NodeWithScore(
                    node=TextNode(
                        text=article_node.node.get_content(),
                        id_=article_node.node.node_id,
                        metadata=article_node.node.metadata,
                    ),
                    score=float(final_score),
                )
            )

        return results[: self.top_k]

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        return asyncio.run(self._aretrieve(query_bundle))


class LegalRAGPipeline:
    """
    Article-first RAG Pipeline:
    - retrieve full articles
    - generate answer from article context
    - emit article-level citations
    """

    def __init__(
        self,
        retriever: LegalHybridRetriever,
        provider: str = "gemini",
        model_name: Optional[str] = None,
        llm: Optional[Any] = None,
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
            query_str=query_str,
        )

        response = await self.client.generate_content_async(prompt)

        citations = []
        for n in nodes:
            citations.append(
                {
                    "source": f"{n.node.metadata.get('so_ky_hieu')} - {n.node.metadata.get('article_title')}",
                    "text": n.node.get_content()[:300] + "...",
                    "score": float(n.score),
                }
            )

        return {
            "answer": response.text,
            "citations": citations,
            "detected_domains": [],
            "confidence_score": 0.0,
        }

    async def astream_query(self, query_str: str) -> AsyncGenerator[str, None]:
        """Stream the RAG response."""
        nodes = await self.retriever.aretrieve(query_str)

        context_str = _build_context_str(nodes)

        prompt = self.qa_prompt_template.format(
            context_str=context_str,
            query_str=query_str,
        )

        async for chunk in self.client.astream_query(prompt):
            if chunk.text:
                yield chunk.text
