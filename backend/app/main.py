from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models import AnalyzeRequest, IngestRequest, IngestResponse, QueryRequest, QueryResponse
from .rag import agentic_chunk, build_graph, compose_answer, detect_anomalies, retrieve
from .store import all_chunks, reset_store, upsert_document

app = FastAPI(title="MoRA-RAG GNN MVP", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


DEMO_DOCS = [
    IngestRequest(
        title="花蓮地震災後調查摘要",
        source="demo-report",
        text=(
            "2024年04月03日於花蓮發生強震，部分道路中斷，邊坡出現落石與崩塌。"
            "調查人員在太魯閣沿線觀察到橋梁伸縮縫受損，震度達6級。"
            "報告指出液化現象集中於河口沖積層，需比對歷史地震資料。"
        ),
    ),
    IngestRequest(
        title="南部豪雨淹水與邊坡監測",
        source="demo-report",
        text=(
            "2025年08月12日於高雄山區累積雨量達620mm，低窪區域淹水，道路排水不足。"
            "在六龜附近邊坡監測到滑動位移12cm，土石流潛勢溪流警戒提高。"
            "雖初報稱無災損，但後續表格記錄一座便橋沖毀並造成交通中斷。"
        ),
    ),
    IngestRequest(
        title="內陸海嘯通報疑義案例",
        source="demo-anomaly",
        text=(
            "2025年09月01日於南投山區通報海嘯災情，紀錄未提及海岸、港口、潮位或沿岸觀測。"
            "資料來源為民眾回報，需與官方災害資料交叉驗證。"
        ),
    ),
]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ingest", response_model=IngestResponse)
def ingest(payload: IngestRequest) -> IngestResponse:
    document, chunks = agentic_chunk(payload.title, payload.text, payload.source)
    upsert_document(document, chunks)
    return IngestResponse(document=document, chunks=chunks, graph=build_graph(all_chunks()))


@app.post("/api/query", response_model=QueryResponse)
def query(payload: QueryRequest) -> QueryResponse:
    chunks = all_chunks()
    router, budget, evidences = retrieve(payload.query, chunks, payload.top_k)
    anomalies = detect_anomalies(chunks)
    pipeline = [
        {"id": "query", "label": "Query", "status": "done"},
        {"id": "router", "label": "MoR Router", "status": "done", "detail": router},
        {"id": "retrieval", "label": "Hybrid Retrieval", "status": "done", "detail": budget},
        {"id": "rerank", "label": "Cross-encoder Rerank", "status": "simulated"},
        {"id": "evaluate", "label": "Evidence Evaluator", "status": "done"},
        {"id": "anomaly", "label": "Graph Anomaly", "status": "done"},
        {"id": "answer", "label": "Final Answer", "status": "done"},
    ]
    return QueryResponse(
        answer=compose_answer(payload.query, evidences, anomalies),
        router=router,
        retrieval_budget=budget,
        evidences=evidences,
        graph=build_graph(chunks),
        anomalies=anomalies,
        pipeline=pipeline,
    )


@app.post("/api/analyze")
def analyze(payload: AnalyzeRequest) -> dict:
    _document, chunks = agentic_chunk(payload.title, payload.text, payload.source)
    graph = build_graph(chunks)
    anomalies = detect_anomalies(chunks)
    return {"chunks": [chunk.model_dump() for chunk in chunks], "graph": graph, "anomalies": [item.model_dump() for item in anomalies]}


@app.post("/api/demo/seed")
def seed_demo() -> dict[str, int]:
    reset_store()
    for doc in DEMO_DOCS:
        document, chunks = agentic_chunk(doc.title, doc.text, doc.source)
        upsert_document(document, chunks)
    return {"documents": len(DEMO_DOCS), "chunks": len(all_chunks())}
