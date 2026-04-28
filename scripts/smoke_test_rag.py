import asyncio
import os
from dotenv import load_dotenv
from core.classifier import LegalQueryClassifier
from retrievers.sqlite_retriever import SQLiteFTS5Retriever
from retrievers.qdrant_retriever import QdrantRetriever
from core.rag_pipeline import LegalRAGPipeline, LegalHybridRetriever

import logging

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def smoke_test():
    print("Initializing components...")
    
    # Use environment variables for providers
    classifier_provider = os.getenv("CLASSIFIER_PROVIDER", "groq")
    classifier_model = os.getenv("CLASSIFIER_MODEL", "llama-3.1-8b-instant")
    
    generation_provider = os.getenv("GENERATION_PROVIDER", "groq")
    generation_model = os.getenv("GENERATION_MODEL", "llama-3.3-70b-versatile")

    classifier = LegalQueryClassifier(
        provider=classifier_provider,
        model_name=classifier_model
    )
    v_retriever = QdrantRetriever()
    f_retriever = SQLiteFTS5Retriever()
    
    hybrid_retriever = LegalHybridRetriever(
        classifier=classifier,
        vector_retriever=v_retriever,
        fts_retriever=f_retriever
    )
    
    pipeline = LegalRAGPipeline(
        retriever=hybrid_retriever,
        provider=generation_provider,
        model_name=generation_model
    )
    
    query = "Thủ tục ly hôn đơn phương cần những giấy tờ gì?"
    print(f"\n[QUERY]: {query}")
    print(f"[LLM]: {generation_provider} ({generation_model})")
    print("-" * 50)
    
    print("Đang xử lý (Classification -> Retrieval -> Generation)...")
    
    try:
        # 1. Test standard response
        result = await pipeline.acustom_query(query)
        print("\n[ANSWER]:")
        print(result["answer"])
        
        print("\n[CITATIONS]:")
        for i, cite in enumerate(result["citations"]):
            print(f"{i+1}. {cite['source']}")
            
        # 2. Test streaming response
        print("\n" + "="*50)
        print("Testing Stream Output:")
        print("="*50)
        async for chunk in pipeline.astream_query(query):
            print(chunk, end="", flush=True)
        print("\n" + "="*50)
        
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(smoke_test())
