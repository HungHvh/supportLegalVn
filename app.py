import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from unittest.mock import AsyncMock, MagicMock
import traceback

import llama_index.core
from torch.cuda import device

llama_index.core.global_handler = None

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize singletons
    print("Initializing RAG Pipeline singletons...")
    try:
        from core.classifier import LegalQueryClassifier
        from retrievers.sqlite_retriever import SQLiteFTS5Retriever
        from retrievers.qdrant_retriever import QdrantRetriever
        from core.rag_pipeline import LegalRAGPipeline, LegalHybridRetriever
        
        classifier_provider = os.getenv("CLASSIFIER_PROVIDER", "groq")
        classifier_fallback_provider = os.getenv("CLASSIFIER_FALLBACK_PROVIDER", "gemini")
        classifier_model = os.getenv("CLASSIFIER_MODEL", "llama-3.1-8b-instant")

        classifier = LegalQueryClassifier(
            provider=classifier_provider,
            fallback_provider=classifier_fallback_provider,
            model_name=classifier_model,
        )
        v_retriever = QdrantRetriever()
        # Pre-create Qdrant client to avoid first-request setup latency.
        # Block startup until client created so the first request does not pay init cost.
        try:
            import asyncio as _asyncio
            # run client initialization in a thread but await it so startup waits
            await _asyncio.to_thread(v_retriever._get_client)
            print("[Startup] Qdrant client initialized during startup")
        except Exception as e:
            print(f"[Warning] Pre-init Qdrant client failed during startup: {e}")
        f_retriever = SQLiteFTS5Retriever()
        
        hybrid_retriever = LegalHybridRetriever(
            classifier=classifier,
            vector_retriever=v_retriever,
            fts_retriever=f_retriever
        )
        
        generation_provider = os.getenv("GENERATION_PROVIDER", "groq")
        generation_model = os.getenv("GENERATION_MODEL", "llama-3.1-70b")
        
        app.state.pipeline = LegalRAGPipeline(
            retriever=hybrid_retriever, 
            provider=generation_provider,
            model_name=generation_model
        )
        print("RAG Pipeline ready.")
    except Exception as e:
        print(f"WARNING: RAG Pipeline failed to initialize: {e}")
        traceback.print_exc()
        print("Backend will start in MOCK mode for API verification.")
        # Create a mock pipeline for verification
        mock = MagicMock()
        mock.acustom_query = AsyncMock(return_value={"answer": "MOCK_MODE_ACTIVE", "citations": []})
        app.state.pipeline = mock

    yield

app = FastAPI(
    title="Legal Support VN API",
    description="Vietnamese Legal RAG System API",
    version="1.0.0",
    lifespan=lifespan
)

from google.api_core import exceptions

@app.exception_handler(exceptions.ResourceExhausted)
async def rate_limit_handler(request: Request, exc: exceptions.ResourceExhausted):
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Gemini API quota exceeded. Retries failed. Please try again later.",
            "retry_after": "60" # Default suggestion
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"CRITICAL ERROR: {str(exc)}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "traceback": traceback.format_exc()}
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
    return {"status": "healthy", "service": "legal-api"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
