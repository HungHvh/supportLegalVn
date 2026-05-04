from pydantic import BaseModel, Field
from typing import List, Optional

class Citation(BaseModel):
    source: str = Field(..., description="Document number or title of the legal source")
    text: str = Field(..., description="Excerpt or snippet from the legal document")
    score: float = Field(..., description="Relevance score (RRF)")
    article_uuid: Optional[str] = Field(None, description="UUID of the canonical article")

class AskRequest(BaseModel):
    query: str = Field(..., example="Thủ tục thành lập công ty TNHH")

class AskResponse(BaseModel):
    answer: str = Field(..., description="IRAC formatted response from the AI")
    citations: List[Citation] = Field(default_factory=list)
    detected_domains: List[str] = Field(default_factory=list)
    confidence_score: float = 0.0

class HealthResponse(BaseModel):
    status: str
    version: str
    db_connected: bool
    qdrant_connected: bool


class ArticleResult(BaseModel):
    article_uuid: str
    doc_id: Optional[str] = None
    so_ky_hieu: Optional[str] = None
    title: Optional[str] = None
    score: float = 0.0
    full_content: str = ""
    doc_type: Optional[str] = None
    highlighted_content: Optional[str] = None


class SearchArticlesRequest(BaseModel):
    query: Optional[str] = None
    article_uuid: Optional[str] = None
    doc_type: Optional[str] = None
    top_k: Optional[int] = 10


class SearchArticlesResponse(BaseModel):
    query: str
    top_results_count: int
    results: List[ArticleResult]
    status: str

