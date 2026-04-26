import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from unittest.mock import AsyncMock, MagicMock

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize singletons
    print("Initializing RAG Pipeline singletons...")
    
    try:
        # 1. Initialize Components
        from core.rag_pipeline import LegalRAGPipeline
        from core.classifier import LegalQueryClassifier
        from retrievers.qdrant_retriever import QdrantRetriever
        from retrievers.sqlite_retriever import SQLiteFTS5Retriever
        from llama_index.llms.gemini import Gemini
        
        classifier = LegalQueryClassifier()
        v_retriever = QdrantRetriever()
        f_retriever = SQLiteFTS5Retriever()
        
        from core.rag_pipeline import LegalHybridRetriever
        hybrid_retriever = LegalHybridRetriever(
            classifier=classifier,
            vector_retriever=v_retriever,
            fts_retriever=f_retriever
        )
        
        llm = Gemini(model="models/gemini-1.5-flash")
        app.state.pipeline = LegalRAGPipeline(retriever=hybrid_retriever, llm=llm)
        print("RAG Pipeline ready.")
    except Exception as e:
        print(f"WARNING: RAG Pipeline failed to initialize: {e}")
        print("Backend will start in MOCK mode for API verification.")
        # Create a mock pipeline for verification
        mock = MagicMock()
        mock.acustom_query = AsyncMock(return_value={"answer": "MOCK_MODE_ACTIVE", "citations": []})
        app.state.pipeline = mock

    yield
    
    # Shutdown: Clean up resources
    print("Shutting down...")

app = FastAPI(
    title="supportLegal Backend",
    description="Vietnamese Legal RAG API",
    version="1.0.0",
    lifespan=lifespan
)

# Include Routers
from api.v1.endpoints import router as api_v1
app.include_router(api_v1, prefix="/api/v1", tags=["v1"])

# CORS Configuration
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
