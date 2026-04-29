import asyncio
import os
from dotenv import load_dotenv
from core.rag_pipeline import LegalHybridRetriever, LegalRAGPipeline
from core.classifier import LegalQueryClassifier
from retrievers.sqlite_retriever import SQLiteFTS5Retriever
from retrievers.qdrant_retriever import QdrantRetriever

async def test_retrieval():
    load_dotenv()
    
    # 1. Setup retrievers
    classifier = LegalQueryClassifier()
    vector_retriever = QdrantRetriever(top_k=50)
    fts_retriever = SQLiteFTS5Retriever(top_k=50)
    
    hybrid_retriever = LegalHybridRetriever(
        classifier=classifier,
        vector_retriever=vector_retriever,
        fts_retriever=fts_retriever,
        top_k=5
    )
    
    pipeline = LegalRAGPipeline(retriever=hybrid_retriever)
    
    # 2. Test query
    query = "xử phạt vi phạm"
    print(f"\n🔍 Testing query: {query}")
    
    results = await hybrid_retriever.aretrieve(query)
    
    print(f"✅ Found {len(results)} articles.")
    for i, res in enumerate(results):
        print(f"\n--- Result {i+1} (Score: {res.score:.4f}) ---")
        print(f"Source: {res.node.metadata.get('so_ky_hieu')}")
        print(f"Title: {res.node.metadata.get('article_title')}")
        print(f"Content length: {len(res.node.text)} characters")
        print(f"Snippet: {res.node.text[:200]}...")

    # 3. Test full pipeline
    print(f"\n🚀 Testing RAG generation...")
    rag_response = await pipeline.acustom_query(query)
    print(f"\n🤖 RAG Answer:\n{rag_response['answer']}")
    print(f"\n📚 Citations:")
    for cit in rag_response['citations']:
        print(f"- {cit['source']} (Score: {cit['score']:.4f})")

if __name__ == "__main__":
    asyncio.run(test_retrieval())
