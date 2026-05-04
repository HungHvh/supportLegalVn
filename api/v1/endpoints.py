from fastapi import APIRouter, Request, HTTPException
from sse_starlette.sse import EventSourceResponse
import json
import asyncio
import time
import logging

from api.models import AskRequest, AskResponse, HealthResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class TestRAGRequest(BaseModel):
    query: str

router = APIRouter()

@router.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest, fastapi_req: Request):
    pipeline = fastapi_req.app.state.pipeline
    result = await pipeline.acustom_query(request.query)
    return result

@router.post("/stream")
async def stream_ask(request: AskRequest, fastapi_req: Request):
    pipeline: fastapi_req.app.state.pipeline
    
    async def event_generator():
        try:
            # We stream tokens first
            async for token in pipeline.astream_query(request.query):
                yield {
                    "event": "message",
                    "data": json.dumps({"token": token})
                }
            
            # In a real implementation, we might want to send 
            # metadata in the last frame. 
            # For this POC, we'll just end the stream.
            yield {
                "event": "done",
                "data": json.dumps({"status": "completed"})
            }
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"detail": str(e)})
            }

    return EventSourceResponse(event_generator())

@router.get("/health", response_model=HealthResponse)
async def health():
    # Basic health check
    return {
        "status": "ok",
        "version": "1.0.0",
        "db_connected": True, # Should be verified with real ping
        "qdrant_connected": True # Should be verified with real ping
    }

@router.post("/test-rag")
async def test_rag_endpoint(request: TestRAGRequest, fastapi_req: Request):
    """
    Isolated RAG performance test — bypass Classifier and LLM.
    Purpose: Measure embedding + Qdrant retrieval latency for performance testing.
    
    Request: {"query": "Tội trộm cắp tài sản"}
    Response: {"query": str, "top_results_count": int, "elapsed_ms": float, "status": str}
    """
    if not request.query or len(request.query.strip()) == 0:
        raise HTTPException(status_code=400, detail="query cannot be empty")
    
    start_time = time.time()
    query = request.query.strip()
    
    try:
        logger.info(f"TEST_RAG_ENDPOINT_START query={query[:50]}")
        pipeline = fastapi_req.app.state.pipeline
        
        # Call retrieve_only for isolated RAG core measurement
        results = await pipeline.retrieve_only(query, top_k=5)
        
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"TEST_RAG_ENDPOINT_COMPLETE elapsed={elapsed:.2f}ms results={len(results)}")
        
        return {
            "query": query,
            "top_results_count": len(results),
            "results": results,
            "elapsed_ms": elapsed,
            "status": "success"
        }
    
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Request timeout after 30 seconds")
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Qdrant unavailable: {str(e)}")
    except Exception as e:
        logger.error(f"test_rag_endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/test-classifier")
async def test_classifier_endpoint(request: TestRAGRequest, fastapi_req: Request):
    """
    Isolated Classifier performance test.
    """
    if not request.query or len(request.query.strip()) == 0:
        raise HTTPException(status_code=400, detail="query cannot be empty")
    
    start_time = time.time()
    query = request.query.strip()
    
    try:
        logger.info(f"TEST_CLASSIFIER_ENDPOINT_START query={query[:50]}")
        pipeline = fastapi_req.app.state.pipeline
        classifier = pipeline.retriever.classifier
        
        classification = await classifier.classify(query)
        
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"TEST_CLASSIFIER_ENDPOINT_COMPLETE elapsed={elapsed:.2f}ms")
        
        return {
            "query": query,
            "domains": classification.domains,
            "confidence": classification.confidence,
            "is_explicit_filter": classification.is_explicit_filter,
            "elapsed_ms": elapsed,
            "provider": classifier.provider,
            "status": "success"
        }
    
    except Exception as e:
        logger.error(f"test_classifier_endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
