from fastapi import APIRouter, Request, HTTPException
from sse_starlette.sse import EventSourceResponse
import json
import asyncio
import time
import logging

from api.models import AskRequest, AskResponse, HealthResponse, SearchArticlesRequest, SearchArticlesResponse
from pydantic import BaseModel
from typing import Optional

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


@router.post("/search-articles", response_model=SearchArticlesResponse)
async def search_articles(request: SearchArticlesRequest, fastapi_req: Request):
    """
    Search articles (legal provisions) and return full canonical article rows
    to be used by frontends (RAG source attribution / show full content).

    Request options:
    - {"query": "text"} -> runs the article-first hybrid retriever and returns top_k articles
    - {"article_uuid": "..."} -> fetches the canonical article by UUID

    Response: {"query": str, "top_results_count": int, "results": [...]} where each
    result contains article_uuid, title, so_ky_hieu, score, full_content, doc_id
    """
    if (not request.query or len(request.query.strip()) == 0) and not request.article_uuid:
        raise HTTPException(status_code=400, detail="Either 'query' or 'article_uuid' must be provided")

    pipeline = fastapi_req.app.state.pipeline

    try:
        import re
        if request.article_uuid:
            # Fetch canonical article by uuid
            articles = await pipeline.retriever.fts_retriever.get_articles_by_uuids([request.article_uuid])
            nodes = articles
        else:
            q = request.query.strip()
            top_k = int(request.top_k or 10)
            # Use fts_retriever directly for fast article-level candidate retrieval
            candidate_nodes = await pipeline.retriever.fts_retriever.aretrieve_articles_by_title(
                query_str=q,
                top_k=top_k,
                doc_type=request.doc_type
            )
            
            # Hydrate full content
            nodes = []
            if candidate_nodes:
                uuids = [getattr(n.node, "id_", "") for n in candidate_nodes if getattr(n.node, "id_", "")]
                hydrated = await pipeline.retriever.fts_retriever.get_articles_by_uuids(uuids)
                hydrated_map = {getattr(h.node, "id_", ""): h for h in hydrated}
                
                # Reconstruct keeping original scores
                for c_node in candidate_nodes:
                    uuid = getattr(c_node.node, "id_", "")
                    if uuid in hydrated_map:
                        h_node = hydrated_map[uuid]
                        h_node.score = getattr(c_node, "score", 0.0)
                        nodes.append(h_node)

        top_k = int(request.top_k or 10)
        nodes = nodes[:top_k]

        formatted = []
        for node in nodes:
            meta = getattr(node.node, "metadata", {}) or {}
            # Try to get full content, fall back to node text
            try:
                content = node.node.get_content()
            except Exception:
                content = getattr(node.node, "text", "")

            # Regex highlighting
            highlighted_content = content
            if request.query and len(request.query.strip()) > 0:
                pattern = re.compile(re.escape(request.query.strip()), re.IGNORECASE)
                highlighted_content = pattern.sub(lambda m: f"<b>{m.group(0)}</b>", content)

            # Determine doc_type from so_ky_hieu if doc_type was requested but not explicitly in metadata
            doc_type_val = request.doc_type
            so_ky_hieu = meta.get("so_ky_hieu") or ""
            if not doc_type_val and so_ky_hieu:
                if "Luật" in so_ky_hieu:
                    doc_type_val = "Luật"
                elif "NĐ-CP" in so_ky_hieu:
                    doc_type_val = "Nghị định"
                elif "TT-" in so_ky_hieu:
                    doc_type_val = "Thông tư"

            formatted.append({
                "article_uuid": meta.get("article_uuid") or node.node.node_id,
                "doc_id": meta.get("doc_id"),
                "so_ky_hieu": so_ky_hieu,
                "title": meta.get("article_title") or "",
                "score": float(getattr(node, "score", 0.0)),
                "full_content": content,
                "doc_type": doc_type_val,
                "highlighted_content": highlighted_content
            })

        return {
            "query": request.query or request.article_uuid,
            "top_results_count": len(formatted),
            "results": formatted,
            "status": "success",
        }

    except Exception as e:
        logger.error(f"search_articles error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


