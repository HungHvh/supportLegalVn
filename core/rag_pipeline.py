import os
import asyncio
import aiosqlite
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple

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


def _unique_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _node_article_uuid(node: NodeWithScore) -> str:
    return str(node.node.metadata.get("article_uuid") or node.node.node_id)


def _build_context_str(nodes: List[NodeWithScore]) -> str:
    return "\n\n".join(
        f"Văn bản: {n.node.metadata.get('so_ky_hieu')} - {n.node.metadata.get('article_title')}\n"
        f"Nội dung:\n{n.node.get_content()}"
        for n in nodes
    )


def _build_article_rerank_text(node: TextNode, max_chars: int = 4000) -> str:
    title = node.metadata.get("article_title") or node.metadata.get("so_ky_hieu") or ""
    content = node.get_content() or ""
    content = " ".join(content.split())
    if len(content) > max_chars:
        content = content[:max_chars]
    return f"{title}\n{content}".strip()


class LegalHybridRetriever(BaseRetriever):
    """
    Article-first hybrid retriever.

    Primary path:
    1. Qdrant semantic search over legal_articles.
    2. SQLite BM25 over article titles.
    3. Fuse article candidates.
    4. Rerank article candidates.

    Legacy fallback:
    5. Chunk-level vector + FTS search, then map back to article candidates.
    """

    def __init__(
        self,
        classifier: LegalQueryClassifier,
        vector_retriever: QdrantRetriever,
        fts_retriever: SQLiteFTS5Retriever,
        db_path: str = "legal_poc.db",
        rrf_k: int = 60,
        top_k: int = 5,
        article_top_k: int = 20,
        title_bm25_top_k: int = 20,
        rerank_input_size: int = 30,
        use_classifier: bool = True,
        use_fts_fallback: bool = True,
    ):
        self.classifier = classifier
        self.vector_retriever = vector_retriever
        self.fts_retriever = fts_retriever
        self.db_path = db_path
        self.rrf_k = rrf_k
        self.top_k = top_k
        self.article_top_k = article_top_k
        self.title_bm25_top_k = title_bm25_top_k
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

    def _accumulate_rrf(
        self,
        results: List[NodeWithScore],
        fused_scores: Dict[str, float],
        node_by_uuid: Dict[str, NodeWithScore],
    ) -> None:
        for rank, res in enumerate(results):
            article_uuid = _node_article_uuid(res)
            fused_scores[article_uuid] = fused_scores.get(article_uuid, 0.0) + 1.0 / (
                self.rrf_k + rank + 1
            )
            if article_uuid not in node_by_uuid:
                node_by_uuid[article_uuid] = res

    async def _legacy_chunk_fallback(self, query_bundle: QueryBundle, query_str: str) -> List[NodeWithScore]:
        legacy_chunk_nodes = await asyncio.gather(
            self.vector_retriever.aretrieve_with_filter(query_bundle),
            self.fts_retriever.aretrieve(query_str),
        )

        fused_chunk_scores: Dict[str, float] = {}
        article_uuid_to_score: Dict[str, float] = {}

        for source_nodes in legacy_chunk_nodes:
            for rank, res in enumerate(source_nodes):
                cid = res.node.node_id
                fused_chunk_scores[cid] = fused_chunk_scores.get(cid, 0.0) + 1.0 / (
                    self.rrf_k + rank + 1
                )
                article_uuid = res.node.metadata.get("article_uuid")
                if article_uuid:
                    article_uuid_to_score[article_uuid] = max(
                        article_uuid_to_score.get(article_uuid, 0.0),
                        fused_chunk_scores[cid],
                    )

        if not article_uuid_to_score:
            return []

        top_article_uuids = sorted(
            article_uuid_to_score,
            key=article_uuid_to_score.get,
            reverse=True,
        )[: self.top_k]

        if not top_article_uuids:
            return []

        articles = await self.fts_retriever.get_articles_by_uuids(top_article_uuids)
        article_map = {n.node.metadata.get("article_uuid"): n for n in articles}

        results: List[NodeWithScore] = []
        for aid in top_article_uuids:
            article_node = article_map.get(aid)
            if article_node is None:
                continue
            results.append(
                NodeWithScore(
                    node=TextNode(
                        text=article_node.node.get_content(),
                        id_=article_node.node.node_id,
                        metadata=article_node.node.metadata,
                    ),
                    score=float(article_uuid_to_score.get(aid, 0.0)),
                )
            )

        return results

    async def _retrieve_article_candidates(
        self,
        query_bundle: QueryBundle,
        query_str: str,
    ) -> List[NodeWithScore]:
        """
        Primary retrieval path: Qdrant article semantic search + BM25 on article title.
        """
        qdrant_task = self.vector_retriever.aretrieve_articles(
            query_bundle,
            top_k=self.article_top_k,
        )
        bm25_task = self.fts_retriever.aretrieve_articles_by_title(
            query_str,
            top_k=self.title_bm25_top_k,
        )

        article_nodes, title_nodes = await asyncio.gather(qdrant_task, bm25_task)

        if not article_nodes and not title_nodes:
            if not self.use_fts_fallback:
                return []
            return await self._legacy_chunk_fallback(query_bundle, query_str)

        fused_scores: Dict[str, float] = {}
        node_by_uuid: Dict[str, NodeWithScore] = {}

        self._accumulate_rrf(article_nodes, fused_scores, node_by_uuid)
        self._accumulate_rrf(title_nodes, fused_scores, node_by_uuid)

        if not fused_scores:
            return []

        ranked_article_uuids = sorted(
            fused_scores,
            key=fused_scores.get,
            reverse=True,
        )[: max(self.article_top_k, self.title_bm25_top_k, self.rerank_input_size)]

        results: List[NodeWithScore] = []
        for aid in ranked_article_uuids:
            node = node_by_uuid.get(aid)
            if node is None:
                continue
            results.append(
                NodeWithScore(
                    node=node.node,
                    score=float(fused_scores.get(aid, 0.0)),
                )
            )

        return results

    async def _aretrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        query_str = query_bundle.query_str

        if self.use_classifier and self.classifier is not None:
            try:
                _classification = await self.classifier.classify(query_str)
                _domains = getattr(_classification, "domains", []) or []
            except Exception:
                pass

        article_candidates = await self._retrieve_article_candidates(query_bundle, query_str)
        if not article_candidates:
            return []

        if self._reranker is not None:
            rerank_pool = article_candidates[: self.rerank_input_size]
            valid_pairs: List[Tuple[str, str]] = []
            valid_nodes: List[NodeWithScore] = []

            for candidate in rerank_pool:
                content = _build_article_rerank_text(candidate.node)
                if content.strip():
                    valid_pairs.append((query_str, content))
                    valid_nodes.append(candidate)

            if valid_pairs:
                scores = self._reranker.predict(valid_pairs)
                reranked = sorted(zip(valid_nodes, scores), key=lambda x: -x[1])
                results = [
                    NodeWithScore(node=item[0].node, score=float(item[1]))
                    for item in reranked[: self.top_k]
                ]
                if results:
                    return results

        # Fallback when reranker is absent or produces no output.
        return article_candidates[: self.top_k]

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
