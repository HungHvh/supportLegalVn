import os
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
from llama_index.core.retrievers import BaseRetriever
from llama_index.core import QueryBundle, Settings, PromptTemplate
from llama_index.core.schema import NodeWithScore

from core.classifier import LegalQueryClassifier
from retrievers.sqlite_retriever import SQLiteFTS5Retriever
from retrievers.qdrant_retriever import QdrantRetriever
from tools.gemini_client import GeminiClient
from tools.groq_client import GroqClient
from tools.deepseek_client import DeepSeekClient
from tools.qwen_dashscope_client import QwenDashScopeClient

class LegalHybridRetriever(BaseRetriever):
    """
    Hybrid retriever that fuses results from SQLite FTS5 and Qdrant Vector search
    using Reciprocal Rank Fusion (RRF). (Async)
    """

    def __init__(
        self, 
        classifier: LegalQueryClassifier,
        vector_retriever: QdrantRetriever,
        fts_retriever: SQLiteFTS5Retriever,
        rrf_k: int = 60,
        top_k: int = 8,
        vector_weight: float = 0.5,
        keyword_weight: float = 0.5,
        use_vector: bool = True,
        use_keyword: bool = True,
        use_classifier: bool = True
    ):
        self.classifier = classifier
        self.vector_retriever = vector_retriever
        self.fts_retriever = fts_retriever
        self.rrf_k = rrf_k
        self.top_k = top_k
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.use_vector = use_vector
        self.use_keyword = use_keyword
        self.use_classifier = use_classifier
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Synchronous version."""
        return asyncio.run(self._aretrieve(query_bundle))

    async def _aretrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Hybrid retrieval with optional ablation toggles."""
        # 1. Classify query (Optional)
        domains = []
        if self.use_classifier:
            try:
                classification = await self.classifier.classify(query_bundle.query_str)
                domains = classification.domains
            except Exception as e:
                print(f"Classification failed: {e}")
        
        # 2. Get results from sources in parallel
        vector_nodes = []
        fts_nodes = []
        
        tasks = []
        if self.use_vector:
            tasks.append(self.vector_retriever.aretrieve_with_filter(query_bundle, domains=domains))
        else:
            tasks.append(asyncio.sleep(0, result=[]))
            
        if self.use_keyword:
            tasks.append(self.fts_retriever.aretrieve(query_bundle))
        else:
            tasks.append(asyncio.sleep(0, result=[]))
        
        vector_nodes, fts_nodes = await asyncio.gather(*tasks)

        # 3. Apply Reciprocal Rank Fusion (RRF)
        fused_scores: Dict[str, Dict[str, Any]] = {}

        def add_to_fusion(nodes: List[NodeWithScore], weight: float):
            for rank, node_with_score in enumerate(nodes):
                node_id = node_with_score.node.node_id
                score = weight / (self.rrf_k + rank + 1)
                if node_id not in fused_scores:
                    fused_scores[node_id] = {
                        "node": node_with_score.node,
                        "score": 0.0
                    }
                fused_scores[node_id]["score"] += score
        
        if vector_nodes:
            add_to_fusion(vector_nodes, self.vector_weight)
        if fts_nodes:
            add_to_fusion(fts_nodes, self.keyword_weight)

        # 4. Sort and return top-k
        sorted_nodes = sorted(
            fused_scores.values(), 
            key=lambda x: x["score"], 
            reverse=True
        )
        
        return [
            NodeWithScore(node=item["node"], score=item["score"]) 
            for item in sorted_nodes[:self.top_k]
        ]

class LegalRAGPipeline:
    """
    Unified Legal RAG Pipeline supporting multiple LLM providers.
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
            "Hãy trả lời câu hỏi của người dùng dựa trên các tài liệu pháp luật được cung cấp dưới đây.\n"
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
        
        context_str = "\n\n".join([
            f"Văn bản: {n.node.metadata.get('so_ky_hieu')}\nNội dung: {n.node.get_content()}" 
            for n in nodes
        ])
        
        prompt = self.qa_prompt_template.format(
            context_str=context_str, 
            query_str=query_str
        )
        
        response = await self.client.generate_content_async(prompt)
        
        # Prepare structured response
        citations = []
        for n in nodes:
            citations.append({
                "source": n.node.metadata.get("so_ky_hieu"),
                "text": n.node.get_content()[:200] + "...",
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
        
        context_str = "\n\n".join([
            f"Văn bản: {n.node.metadata.get('so_ky_hieu')}\nNội dung: {n.node.get_content()}" 
            for n in nodes
        ])
        
        prompt = self.qa_prompt_template.format(
            context_str=context_str, 
            query_str=query_str
        )
        
        async for chunk in self.client.astream_query(prompt):
            if chunk.text:
                yield chunk.text
