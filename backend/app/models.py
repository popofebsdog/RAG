from __future__ import annotations

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    title: str = Field(..., min_length=1)
    text: str = Field(..., min_length=10)
    source: str = "manual"


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(6, ge=1, le=20)


class AnalyzeRequest(BaseModel):
    title: str = "incoming-data"
    text: str = Field(..., min_length=5)
    source: str = "incoming"


class Chunk(BaseModel):
    id: str
    document_id: str
    title: str
    text: str
    source: str
    hazards: list[str] = []
    locations: list[str] = []
    dates: list[str] = []
    metrics: list[str] = []
    summary: str = ""


class DocumentRecord(BaseModel):
    id: str
    title: str
    source: str
    chunk_ids: list[str]


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    score: float = 0


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str
    weight: float = 1


class Evidence(BaseModel):
    chunk_id: str
    title: str
    source: str
    text: str
    score: float
    hazards: list[str]
    locations: list[str]
    evaluator: str


class Anomaly(BaseModel):
    id: str
    severity: str
    score: float
    reason: str
    evidence: str
    node_id: str | None = None


class QueryResponse(BaseModel):
    answer: str
    router: dict[str, float]
    retrieval_budget: dict[str, int]
    evidences: list[Evidence]
    graph: dict[str, list[dict]]
    anomalies: list[Anomaly]
    pipeline: list[dict]


class IngestResponse(BaseModel):
    document: DocumentRecord
    chunks: list[Chunk]
    graph: dict[str, list[dict]]
