import os
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
from llama_index.core.retrievers import BaseRetriever
from llama_index.core import QueryBundle, Settings, PromptTemplate
from llama_index.core.schema import NodeWithScore
from llama_index.core.query_engine import CustomQueryEngine
from llama_index.llms.gemini import Gemini
import llama_index.core

from core.classifier import LegalQueryClassifier
from retrievers.sqlite_retriever import SQLiteFTS5Retriever
from retrievers.qdrant_retriever import QdrantRetriever

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
        keyword_weight: float = 0.5
    ):
        self.classifier = classifier
        self.vector_retriever = vector_retriever
        self.fts_retriever = fts_retriever
        self.rrf_k = rrf_k
        self.top_k = top_k
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Synchronous version (not recommended for FastAPI)."""
        return asyncio.run(self._aretrieve(query_bundle))

    async def _aretrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Hybrid retrieval with classification and RRF fusion (Async)."""
        # 1. Classify query
        classification = await self.classifier.classify(query_bundle.query_str)
        domains = classification.domains
        
        # 2. Get results from both sources in parallel
        vector_task = self.vector_retriever.aretrieve_with_filter(
            query_bundle, 
            domains=domains
        )
        fts_task = self.fts_retriever.aretrieve(query_bundle)
        
        vector_nodes, fts_nodes = await asyncio.gather(vector_task, fts_task)

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

        add_to_fusion(vector_nodes, self.vector_weight)
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

class LegalRAGPipeline(CustomQueryEngine):
    """
    Unified Legal RAG Pipeline for Vietnamese Law. (Async & Streaming)
    """
    retriever: LegalHybridRetriever
    llm: Gemini
    qa_prompt: PromptTemplate

    def __init__(self, retriever: LegalHybridRetriever, llm: Gemini):
        qa_prompt_str = (
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
        qa_prompt = PromptTemplate(qa_prompt_str)
        super().__init__(retriever=retriever, llm=llm, qa_prompt=qa_prompt)

    async def acustom_query(self, query_str: str) -> Dict[str, Any]:
        """Execute the full RAG pipeline and return structured JSON."""
        nodes = await self.retriever.aretrieve(query_str)
        
        context_str = "\n\n".join([
            f"Văn bản: {n.node.metadata.get('so_ky_hieu')}\nNội dung: {n.node.get_content()}" 
            for n in nodes
        ])
        
        fmt_prompt = self.qa_prompt.format(
            context_str=context_str, 
            query_str=query_str
        )
        
        response = await self.llm.acomplete(fmt_prompt)
        
        # Prepare structured response
        citations = []
        for n in nodes:
            citations.append({
                "source": n.node.metadata.get("so_ky_hieu"),
                "text": n.node.get_content()[:200] + "...",
                "score": float(n.score)
            })
            
        return {
            "answer": str(response),
            "citations": citations,
            "detected_domains": [], # To be filled if classifier returns them
            "confidence_score": 0.0 # Placeholder
        }

    async def astream_query(self, query_str: str) -> AsyncGenerator[str, None]:
        """Stream the RAG response token by token."""
        nodes = await self.retriever.aretrieve(query_str)
        
        context_str = "\n\n".join([
            f"Văn bản: {n.node.metadata.get('so_ky_hieu')}\nNội dung: {n.node.get_content()}" 
            for n in nodes
        ])
        
        fmt_prompt = self.qa_prompt.format(
            context_str=context_str, 
            query_str=query_str
        )
        
        gen = await self.llm.astream_complete(fmt_prompt)
        async for response in gen:
            yield response.delta

        # Final frame with metadata could be added here in a real SSE implementation
        # For now, we just stream tokens.

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    async def test():
        classifier = LegalQueryClassifier()
        v_retriever = QdrantRetriever()
        f_retriever = SQLiteFTS5Retriever()
        
        hybrid_retriever = LegalHybridRetriever(
            classifier=classifier,
            vector_retriever=v_retriever,
            fts_retriever=f_retriever
        )
        
        llm = Gemini(model="models/gemini-1.5-flash")
        pipeline = LegalRAGPipeline(retriever=hybrid_retriever, llm=llm)
        
        query = "Thủ tục thành lập công ty TNHH"
        print(f"Querying: {query}")
        res = await pipeline.acustom_query(query)
        print(f"Answer: {res['answer'][:100]}...")
        print(f"Citations: {len(res['citations'])}")

    asyncio.run(test())
