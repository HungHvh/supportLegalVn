from fastapi import APIRouter, Request, HTTPException
from sse_starlette.sse import EventSourceResponse
import json
import asyncio

from api.models import AskRequest, AskResponse, HealthResponse
# from core.rag_pipeline import LegalRAGPipeline (Deferred to avoid torch import error)

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
