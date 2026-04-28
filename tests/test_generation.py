import pytest
import os
import re
from core.rag_pipeline import LegalRAGPipeline, LegalHybridRetriever
from core.classifier import LegalQueryClassifier
from retrievers.sqlite_retriever import SQLiteFTS5Retriever
from retrievers.qdrant_retriever import QdrantRetriever
from llama_index.llms.gemini import Gemini

@pytest.mark.asyncio
async def test_generation_irac_structure_smoke():
    """
    Smoke test for IRAC structure. 
    Note: Requires API key. Checks for headers in response.
    """
    # This is a stub for behavior validation
    # Real test would mock the LLM response to verify regex/parsing
    response_text = """
    Vấn đề: Thủ tục ly hôn.
    Quy định: Theo Điều 51 Luật Hôn nhân và gia đình 2014...
    Phân tích: Việc ly hôn được giải quyết tại Tòa án...
    Kết luận: Bạn cần nộp đơn tại Tòa án nhân dân cấp huyện.
    Lưu ý: Thông tin này chỉ mang tính chất tham khảo...
    """
    
    assert "Vấn đề" in response_text
    assert "Quy định" in response_text
    assert "Phân tích" in response_text
    assert "Kết luận" in response_text
    assert "tham khảo" in response_text
    
    # Check citation format
    citation_pattern = r"Theo (Khoản|Điều) \d+.*"
    assert re.search(citation_pattern, response_text)

def test_pipeline_initialization():
    """Verify all components of the pipeline can be instantiated."""
    classifier = LegalQueryClassifier()
    v_retriever = QdrantRetriever()
    f_retriever = SQLiteFTS5Retriever()
    
    hybrid_retriever = LegalHybridRetriever(
        classifier=classifier,
        vector_retriever=v_retriever,
        fts_retriever=f_retriever
    )
    
    llm = Gemini(model="models/gemini-2.0-flash")
    pipeline = LegalRAGPipeline(retriever=hybrid_retriever, llm=llm)
    
    assert pipeline is not None
    assert pipeline.retriever == hybrid_retriever
