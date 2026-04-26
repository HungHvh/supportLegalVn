from pydantic import BaseModel, Field
from typing import List, Optional

class Citation(BaseModel):
    source: str = Field(..., description="Document number or title of the legal source")
    text: str = Field(..., description="Excerpt or snippet from the legal document")
    score: float = Field(..., description="Relevance score (RRF)")

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
