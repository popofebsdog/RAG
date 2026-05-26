from __future__ import annotations

import os
import json
import re
import tempfile
import time
from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

load_dotenv(override=True)

from rag.chunking import Chunk, chunk_pages
from rag.embedding import embed_chunks, embed_query
from rag.anomaly import detect_graph_out_of_domain, detect_out_of_domain, detect_relation_contradiction
from rag.graph_analysis import GraphAnalysisResult, build_similarity_graph
from rag.graph_store import clear_graphs, list_graphs, read_graph, save_graph
from rag.image_store import clear as clear_images, get_images, remove_doc as remove_images, store_images
from rag.knowledge_extraction import ExtractedKnowledgeGraph, extract_knowledge_graph
from rag.keyword_extract import extract_keywords
from rag.llm import generate_answer
from rag.loader import PyMuPDFLoader, get_loader
from rag.markdown_store import (
    anchor_pages,
    clear as clear_markdown,
    first_anchor,
    get_anchors,
    get_markdown,
    remove_doc as remove_markdown,
    store_markdown,
)
from rag.ocr_store import clear as clear_ocr, get_ocr, remove_doc as remove_ocr, store_ocr
from rag.page_store import get_pages, list_docs as list_page_docs, remove_doc as remove_pages, store_pages, clear as clear_pages
from rag.qdrant_store import DocMeta, QdrantStore, get_store, get_image_store
from rag.relations_store import (
    add_relation,
    clear_relations,
    list_relations,
    remove_relation as delete_relation,
    remove_relations_for_chunks,
    update_relation_weight,
)
from rag.retrieval import retrieve
from rag.source_store import clear as clear_sources, get_pdf_path, remove_doc as remove_source, store_pdf
from rag.umap_analysis import compute_umap

app = FastAPI(title="Visual RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5180", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def warm_qdrant_clients() -> None:
    # Qdrant local mode uses a file lock and qdrant-client imports a large model
    # surface. Warm both collections serially so the first parallel browser
    # requests don't race module import or open separate local clients.
    get_store()
    get_image_store()


# ── Response models ──────────────────────────────────────────────────────────

class ChunkInfo(BaseModel):
    chunk_id: str
    text: str
    source_page: int
    start_char: int
    end_char: int
    source_doc: str = ""
    source_anchor: str | None = None
    label: str | None = None
    is_manual: bool = False


class DocInfo(BaseModel):
    filename: str
    chunk_count: int
    region: str | None = None
    year: int | None = None
    perspective: str | None = None


class ProjectFilesResponse(BaseModel):
    files: list[DocInfo]
    total_chunks: int


class IngestResponse(BaseModel):
    filename: str
    total_pages: int
    total_chunks: int
    chunks: list[ChunkInfo]


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    source_page: int
    score: float
    source_doc: str = ""
    source_anchor: str | None = None
    label: str | None = None
    is_manual: bool = False
    is_boosted: bool = False   # True when manual-attention boost was applied
    node_type: str = "auto"
    hazard_tags: list[str] = []


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    region: str | None = None
    year: int | None = None
    project_id: str = "default"


class AnomalyFlag(BaseModel):
    type: str   # "out_of_domain" | "insufficient_evidence" | "relation_contradiction"
    message: str
    details: dict = {}


class QueryResponse(BaseModel):
    question: str
    answer: str
    retrieved_chunks: list[RetrievedChunk]
    graph_data: "GraphData"
    anomalies: list[AnomalyFlag] = []
    router: dict[str, float] = {}


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    active: bool = False
    data: dict = {}


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str = ""
    active: bool = False


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


# ── UMAP models ──────────────────────────────────────────────────────────────

class UMAPPointModel(BaseModel):
    chunk_id: str
    x: float
    y: float
    text: str
    source_page: int
    source_doc: str = ""
    label: str | None = None
    node_type: str = "auto"
    is_retrieved: bool = False
    is_manual: bool = False
    score: float = 0.0


class UMAPRequest(BaseModel):
    question: str | None = None
    top_k: int = 5
    region: str | None = None
    year: int | None = None
    project_id: str = "default"


class UMAPResponse(BaseModel):
    points: list[UMAPPointModel]
    query_x: float | None = None
    query_y: float | None = None
    query_label: str | None = None


# ── Graph analysis models ────────────────────────────────────────────────────

class GraphAnalysisNodeModel(BaseModel):
    id: str
    label: str
    keywords: str = ""          # extracted keywords for node display
    page: int
    source_doc: str = ""
    node_type: str = "auto"
    hazard_tags: list[str] = []
    project_id: str = "default"
    degree_centrality: float
    betweenness_centrality: float
    community: int
    text: str
    is_retrieved: bool = False
    is_manual: bool = False


class GraphAnalysisEdgeModel(BaseModel):
    source: str
    target: str
    weight: float


class GraphAnalysisRequest(BaseModel):
    question: str | None = None
    top_k: int = 5
    threshold: float = 0.5
    region: str | None = None
    year: int | None = None
    project_id: str = "default"


class GraphAnalysisResponse(BaseModel):
    nodes: list[GraphAnalysisNodeModel]
    edges: list[GraphAnalysisEdgeModel]
    num_communities: int
    density: float
    manual_relations: list["RelationInfo"] = []


class GraphJsonInfo(BaseModel):
    filename: str
    graph_name: str
    updated_at: int | None = None
    size_bytes: int
    node_count: int = 0
    edge_count: int = 0


class GraphJsonListResponse(BaseModel):
    files: list[GraphJsonInfo]


class RelationRequest(BaseModel):
    from_chunk_id: str
    to_chunk_id: str
    label: str
    weight: float = 1.0
    project_id: str = "default"


class RelationInfo(BaseModel):
    id: str
    from_chunk_id: str
    to_chunk_id: str
    label: str
    weight: float = 1.0
    project_id: str
    created_at: int
    vectorized: bool = True


# ── Manual chunk models ──────────────────────────────────────────────────────

class ManualChunkRequest(BaseModel):
    text: str
    label: str
    source_doc: str = ""
    source_page: int = 0
    source_anchor: str | None = None
    project_id: str = "default"
    region: str | None = None
    year: int | None = None
    perspective: str | None = None


class ManualChunkInfo(BaseModel):
    chunk_id: str
    text: str
    label: str
    source_doc: str
    source_page: int = 0
    source_anchor: str | None = None
    project_id: str = "default"
    region: str | None = None
    year: int | None = None
    perspective: str | None = None


# ── Page models ──────────────────────────────────────────────────────────────

class PageTextModel(BaseModel):
    page_num: int
    text: str


class PDFInfoModel(BaseModel):
    filename: str
    total_pages: int


class MarkdownResponse(BaseModel):
    filename: str
    markdown: str
    anchors: list[dict] = []


class OCRWordModel(BaseModel):
    text: str
    left: float
    top: float
    width: float
    height: float
    conf: float = 0.0


class OCRPageModel(BaseModel):
    page_num: int
    width: int
    height: int
    words: list[OCRWordModel]


class VLMSelectionRequest(BaseModel):
    image_b64: str
    source_doc: str = ""
    source_page: int = 0
    project_id: str = "default"


class VLMSelectionResponse(BaseModel):
    label: str
    description: str
    evidence_type: str = "image_selection"
    source_doc: str = ""
    source_page: int = 0


# ── Helpers ──────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    snippet = re.sub(r"\s+", " ", text.strip())[:24].rstrip()
    return re.sub(r"[^\w\s-]", "", snippet).strip().replace(" ", "-").lower()


def _remove_doc_graph_artifacts(store: QdrantStore, filename: str, project_id: str) -> None:
    """Remove prior graph nodes and relations derived from a document."""
    payloads = store.payloads_by_chunk_id(project_id=project_id)
    chunk_ids = {
        chunk_id
        for chunk_id, payload in payloads.items()
        if payload.get("source_doc") == filename
    }
    if chunk_ids:
        removed_relation_ids = remove_relations_for_chunks(chunk_ids, project_id)
        for relation_id in removed_relation_ids:
            store.remove_relation(relation_id)
    store.remove_doc(filename, project_id=project_id)
    remove_markdown(filename, project_id=project_id)
    remove_source(filename, project_id=project_id)
    remove_ocr(filename, project_id=project_id)
    remove_images(filename, project_id=project_id)
    clear_graphs(project_id)


def _extract_pdf_ocr(path: str) -> list[dict]:
    import fitz
    import pytesseract
    from PIL import Image

    lang = os.getenv("OCR_LANG", "chi_tra+eng")
    dpi = int(os.getenv("OCR_DPI", "150"))
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    doc = fitz.open(path)
    pages: list[dict] = []
    for page_index in range(doc.page_count):
        page = doc[page_index]
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        data = pytesseract.image_to_data(
            image,
            lang=lang,
            config="--psm 6",
            output_type=pytesseract.Output.DICT,
        )
        words: list[dict] = []
        for i, raw_text in enumerate(data.get("text", [])):
            text = str(raw_text).strip()
            if not text:
                continue
            try:
                conf = float(data.get("conf", [0])[i])
            except Exception:
                conf = 0.0
            if conf < 0:
                continue
            words.append({
                "text": text,
                "left": float(data["left"][i]),
                "top": float(data["top"][i]),
                "width": float(data["width"][i]),
                "height": float(data["height"][i]),
                "conf": conf,
            })
        pages.append({
            "page_num": page_index + 1,
            "width": pix.width,
            "height": pix.height,
            "words": words,
        })
    return pages


def _extract_response_text(data: dict) -> str:
    text = data.get("output_text")
    if text:
        return str(text)
    parts: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(str(content["text"]))
    return "\n".join(parts)


def _json_from_text(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return {}


def _describe_vlm_selection(image_b64: str, source_doc: str, source_page: int) -> tuple[str, str, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(500, "OPENAI_API_KEY is required for VLM selection.")

    import httpx

    image_data = image_b64.split(",", 1)[1] if "," in image_b64 else image_b64
    prompt = f"""你正在閱讀災害調查 PDF 中由使用者框選的一小塊影像。
請只根據影像中看得見的文字、照片、表格、標註與圖面判讀，不要補充外部知識，不要編造。

來源文件：{source_doc or "未指定"}
來源頁碼：{source_page or "未指定"}

請輸出 JSON，不能有 Markdown，格式固定：
{{
  "label": "適合成為知識圖譜節點的短標題，12字以內",
  "description": "可直接成為 chunk 的繁體中文內容。要整合影像中的可見文字、數值、位置、地質或因果資訊；若是照片或剖面圖，描述觀察到的證據與可支持的判斷。避免使用「看起來」「可能」除非影像真的不清楚。",
  "evidence_type": "table/photo/map/profile/text/selection"
}}

若框選區域資訊不足，仍然回傳可見內容，但 description 開頭加上「低信心：」。
"""
    payload = {
        "model": os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini"),
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": f"data:image/png;base64,{image_data}"},
                ],
            }
        ],
        "max_output_tokens": int(os.getenv("VLM_SELECTION_MAX_TOKENS", "700")),
    }
    try:
        resp = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=float(os.getenv("VLM_TIMEOUT", "120")),
        )
        resp.raise_for_status()
    except Exception as exc:
        raise HTTPException(500, f"VLM selection failed: {exc}") from exc

    parsed = _json_from_text(_extract_response_text(resp.json()))
    description = str(parsed.get("description") or "").strip()
    label = str(parsed.get("label") or "").strip()
    evidence_type = str(parsed.get("evidence_type") or "selection").strip()
    if not description:
        description = "低信心：VLM 未能可靠辨識此框選區域。請調整框選範圍或手動輸入內容。"
    if not label:
        label = re.sub(r"\s+", "", description[:12]) or "影像節點"
    return label[:40], description, evidence_type[:40]


def _upsert_extracted_knowledge_graph(
    graph: ExtractedKnowledgeGraph,
    source_doc: str,
    project_id: str,
    meta: DocMeta,
) -> None:
    """Persist extracted concept nodes and relation vectors as the initial graph."""
    if not graph.nodes:
        return

    store = get_store()
    existing_by_label = {
        str(payload.get("label")): payload
        for payload in store.manual_chunks(project_id=project_id)
        if payload.get("label")
    }
    node_ids_by_label: dict[str, str] = {}

    for node in graph.nodes:
        if node.label in existing_by_label:
            node_ids_by_label[node.label] = existing_by_label[node.label]["chunk_id"]
            continue
        chunk_id = f"manual:{_slugify(node.label)}:{int(time.time())}"
        chunk = Chunk(
            chunk_id=chunk_id,
            text=node.text,
            source_page=max(0, int(node.page or 0)),
            start_char=0,
            end_char=len(node.text),
            source_doc=source_doc,
            source_anchor=first_anchor(node.text) or (f"^p{int(node.page)}" if node.page else None),
        )
        embedding = embed_query(f"{node.label}: {node.text}")
        store.upsert_manual(chunk, embedding, node.label, meta)
        node_ids_by_label[node.label] = chunk_id

    existing_relations = list_relations(project_id)
    for relation in graph.relations:
        from_id = node_ids_by_label.get(relation.from_label)
        to_id = node_ids_by_label.get(relation.to_label)
        if not from_id or not to_id or from_id == to_id:
            continue
        label = relation.label.strip()
        duplicate = any(
            rel.get("from_chunk_id") == from_id
            and rel.get("to_chunk_id") == to_id
            and str(rel.get("label", "")).strip().casefold() == label.casefold()
            for rel in existing_relations
        )
        if duplicate:
            continue
        new_relation = add_relation(
            from_chunk_id=from_id,
            to_chunk_id=to_id,
            label=label,
            weight=max(0.0, min(1.0, relation.weight)),
            project_id=project_id,
        )
        existing_relations.append(new_relation)
        _upsert_relation_vector(new_relation)


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    store = get_store()
    return {"status": "ok", "indexed_chunks": store.chunk_count}


@app.post("/ingest", response_model=IngestResponse)
async def ingest(
    file: Annotated[UploadFile, File()],
    loader_type: str = Form("pymupdf4llm"),
    chunk_mode: str = Form("semantic"),
    mode: str = Form("append"),
    chunk_strategy: str = Form("auto"),     # "auto" | "manual"
    project_id: str = Form("default"),
    region: str = Form(""),
    year: str = Form(""),
    perspective: str = Form(""),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")

    contents = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        os.environ["PDF_LOADER"] = loader_type
        os.environ["CHUNK_MODE"] = chunk_mode
        loader = get_loader()
        try:
            pages = loader.load(tmp_path)
        except RuntimeError as exc:
            raise HTTPException(502, str(exc)) from exc
        if not pages:
            raise HTTPException(422, "Could not extract text from PDF")
        pages, clean_markdown, anchor_records = anchor_pages(pages)

        # Always store raw pages (Document Reader)
        store_pages(file.filename, pages, project_id=project_id)
        store_markdown(file.filename, clean_markdown, anchor_records, project_id=project_id)

        # Extract and store images (always, regardless of chunk_strategy)
        try:
            img_loader = PyMuPDFLoader()
            page_images = img_loader.load_images(tmp_path)
            store_images(file.filename, page_images, project_id=project_id)
        except Exception:
            pass  # image extraction failure is non-fatal

        # Unified strategy: semantic chunks + extracted concept graph + editable relations.
        chunks = chunk_pages(pages)
        for c in chunks:
            c.source_doc = file.filename
            c.source_anchor = first_anchor(c.text) or f"^p{c.source_page}"

        embeddings = embed_chunks(chunks)
        store = get_store()
        meta = DocMeta(
            region=region or None,
            year=int(year) if year.isdigit() else None,
            perspective=perspective or None,
            project_id=project_id,
        )

        if mode == "replace":
            clear_relations(project_id)
            clear_graphs(project_id)
            store.clear(project_id=project_id)
            clear_pages(project_id=project_id)
            clear_markdown(project_id=project_id)
            clear_sources(project_id=project_id)
            clear_ocr(project_id=project_id)
            clear_images(project_id=project_id)
            get_image_store().clear(project_id=project_id)
        else:
            if file.filename in store.docs(project_id=project_id):
                _remove_doc_graph_artifacts(store, file.filename, project_id)
                remove_pages(file.filename, project_id=project_id)
                remove_markdown(file.filename, project_id=project_id)
                remove_source(file.filename, project_id=project_id)
                remove_ocr(file.filename, project_id=project_id)

        store_pdf(file.filename, contents, project_id=project_id)
        store.upsert(chunks, embeddings, meta)
        store_pages(file.filename, pages, project_id=project_id)
        store_markdown(file.filename, clean_markdown, anchor_records, project_id=project_id)
        extracted_graph = extract_knowledge_graph(pages, file.filename)
        _upsert_extracted_knowledge_graph(extracted_graph, file.filename, project_id, meta)

        chunk_infos = [
            ChunkInfo(
                chunk_id=c.chunk_id,
                text=c.text,
                source_page=c.source_page,
                start_char=c.start_char,
                end_char=c.end_char,
                source_doc=c.source_doc,
                source_anchor=c.source_anchor,
            )
            for c in chunks
        ]
        return IngestResponse(
            filename=file.filename,
            total_pages=len(pages),
            total_chunks=len(chunks),
            chunks=chunk_infos,
        )
    finally:
        os.unlink(tmp_path)


# ── Project management ───────────────────────────────────────────────────────

@app.get("/project/files", response_model=ProjectFilesResponse)
def project_files(project_id: str = "default"):
    store = get_store()
    qdrant_docs = set(store.docs(project_id=project_id))
    page_docs = set(list_page_docs(project_id=project_id))
    all_docs = qdrant_docs | page_docs

    files: list[DocInfo] = [
        DocInfo(filename=doc, chunk_count=store.doc_chunk_count(doc, project_id=project_id))
        for doc in all_docs
    ]

    return ProjectFilesResponse(
        files=files,
        total_chunks=store.chunk_count_for_project(project_id),
    )


@app.delete("/project/clear")
def project_clear(project_id: str = "default"):
    store = get_store()
    relation_ids = [r["id"] for r in list_relations(project_id)]
    store.clear(project_id=project_id)
    clear_pages(project_id=project_id)
    clear_markdown(project_id=project_id)
    clear_sources(project_id=project_id)
    clear_ocr(project_id=project_id)
    clear_images(project_id=project_id)
    get_image_store().clear(project_id=project_id)
    clear_graphs(project_id)
    clear_relations(project_id)
    for relation_id in relation_ids:
        try:
            store.remove_relation(relation_id)
        except Exception:
            pass
    return {"status": "cleared"}


@app.delete("/project/files/{filename}")
def project_remove_file(filename: str, project_id: str = "default"):
    store = get_store()
    qdrant_docs = set(store.docs(project_id=project_id))
    page_docs = set(list_page_docs(project_id=project_id))
    if filename not in qdrant_docs and filename not in page_docs:
        raise HTTPException(404, f"'{filename}' not found in project")
    _remove_doc_graph_artifacts(store, filename, project_id)
    remove_pages(filename, project_id=project_id)
    return {"status": "removed", "filename": filename}


@app.head("/project/files/{filename}/pdf")
def project_pdf_head(filename: str, project_id: str = "default"):
    path = get_pdf_path(filename, project_id=project_id)
    if not path:
        raise HTTPException(404, f"PDF for '{filename}' not found. Re-ingest the file.")
    return Response(status_code=200, media_type="application/pdf")


@app.get("/project/files/{filename}/pdf")
def project_pdf(filename: str, project_id: str = "default"):
    path = get_pdf_path(filename, project_id=project_id)
    if not path:
        raise HTTPException(404, f"PDF for '{filename}' not found. Re-ingest the file.")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="inline",
    )


@app.get("/project/files/{filename}/info", response_model=PDFInfoModel)
def project_pdf_info(filename: str, project_id: str = "default"):
    path = get_pdf_path(filename, project_id=project_id)
    if not path:
        raise HTTPException(404, f"PDF for '{filename}' not found. Re-ingest the file.")
    try:
        import fitz
        doc = fitz.open(path)
        try:
            return PDFInfoModel(filename=filename, total_pages=doc.page_count)
        finally:
            doc.close()
    except Exception as exc:
        raise HTTPException(500, f"PDF info read failed: {exc}") from exc


@app.get("/project/files/{filename}/page-image/{page_num}.png")
def project_pdf_page_image(filename: str, page_num: int, project_id: str = "default", scale: float = 1.8):
    path = get_pdf_path(filename, project_id=project_id)
    if not path:
        raise HTTPException(404, f"PDF for '{filename}' not found. Re-ingest the file.")
    if page_num < 1:
        raise HTTPException(400, "Page number must be >= 1.")
    try:
        import fitz
        doc = fitz.open(path)
        try:
            if page_num > doc.page_count:
                raise HTTPException(404, f"Page {page_num} not found.")
            page = doc.load_page(page_num - 1)
            matrix = fitz.Matrix(max(0.5, min(scale, 3.0)), max(0.5, min(scale, 3.0)))
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            return Response(content=pix.tobytes("png"), media_type="image/png")
        finally:
            doc.close()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"PDF page render failed: {exc}") from exc

@app.get("/project/files/{filename}/ocr", response_model=list[OCRPageModel])
def project_file_ocr(filename: str, project_id: str = "default"):
    cached = get_ocr(filename, project_id=project_id)
    if cached:
        return [OCRPageModel(**page) for page in cached]

    path = get_pdf_path(filename, project_id=project_id)
    if not path:
        raise HTTPException(404, f"PDF for '{filename}' not found. Re-ingest the file.")

    try:
        pages = _extract_pdf_ocr(path)
    except Exception as exc:
        raise HTTPException(500, f"OCR failed: {exc}") from exc
    store_ocr(filename, pages, project_id=project_id)
    return [OCRPageModel(**page) for page in pages]


@app.post("/vlm/selection", response_model=VLMSelectionResponse)
def vlm_selection(req: VLMSelectionRequest):
    label, description, evidence_type = _describe_vlm_selection(
        req.image_b64,
        req.source_doc,
        req.source_page,
    )
    return VLMSelectionResponse(
        label=label,
        description=description,
        evidence_type=evidence_type,
        source_doc=req.source_doc,
        source_page=req.source_page,
    )


@app.get("/project/pages/{filename}", response_model=list[PageTextModel])
def project_pages(filename: str, project_id: str = "default"):
    pages = get_pages(filename, project_id=project_id)
    if not pages:
        raise HTTPException(404, f"Pages for '{filename}' not found. Re-ingest the file.")
    return [PageTextModel(page_num=p["page_num"], text=p["text"]) for p in pages]


@app.get("/project/markdown/{filename}", response_model=MarkdownResponse)
def project_markdown(filename: str, project_id: str = "default"):
    markdown = get_markdown(filename, project_id=project_id)
    if not markdown:
        raise HTTPException(404, f"Markdown for '{filename}' not found. Re-ingest the file.")
    return MarkdownResponse(
        filename=filename,
        markdown=markdown,
        anchors=get_anchors(filename, project_id=project_id),
    )


# ── Page images ──────────────────────────────────────────────────────────────

class PageImageModel(BaseModel):
    page_num: int
    image_index: int
    data_b64: str
    width: int
    height: int


@app.get("/project/pages/{filename}/images", response_model=list[PageImageModel])
def project_page_images(filename: str, project_id: str = "default"):
    images = get_images(filename, project_id=project_id)
    return [PageImageModel(**img) for img in images]


# ── Image chunks ─────────────────────────────────────────────────────────────

class ImageChunkRequest(BaseModel):
    label: str
    source_doc: str
    source_page: int
    image_index: int
    data_b64: str          # the PNG base64 of the image
    project_id: str = "default"


class ImageChunkInfo(BaseModel):
    chunk_id: str
    label: str
    source_doc: str
    source_page: int
    image_index: int
    project_id: str = "default"
    node_type: str = "image"


@app.post("/chunks/image", response_model=ImageChunkInfo)
def create_image_chunk(req: ImageChunkRequest):
    from rag.clip_embedding import embed_image_b64

    if not req.label.strip():
        raise HTTPException(400, "label cannot be empty")

    chunk_id = f"image:{_slugify(req.label)}:{int(time.time())}"

    try:
        embedding = embed_image_b64(req.data_b64)
    except Exception as e:
        raise HTTPException(500, f"CLIP embedding failed: {e}")

    get_image_store().upsert_image(
        chunk_id=chunk_id,
        embedding=embedding,
        label=req.label,
        source_doc=req.source_doc,
        source_page=req.source_page,
        image_index=req.image_index,
        project_id=req.project_id,
    )

    return ImageChunkInfo(
        chunk_id=chunk_id,
        label=req.label,
        source_doc=req.source_doc,
        source_page=req.source_page,
        image_index=req.image_index,
        project_id=req.project_id,
    )


@app.get("/chunks/image", response_model=list[ImageChunkInfo])
def list_image_chunks(project_id: str = "default"):
    payloads = get_image_store().list_chunks(project_id=project_id)
    return [
        ImageChunkInfo(
            chunk_id=p["chunk_id"],
            label=p["label"],
            source_doc=p["source_doc"],
            source_page=p["source_page"],
            image_index=p["image_index"],
            project_id=p["project_id"],
        )
        for p in payloads
    ]


@app.delete("/chunks/image/{chunk_id}")
def delete_image_chunk(chunk_id: str):
    get_image_store().remove_chunk(chunk_id)
    return {"status": "deleted", "chunk_id": chunk_id}


# ── Manual chunks ────────────────────────────────────────────────────────────

@app.post("/chunks/manual", response_model=ManualChunkInfo)
def create_manual_chunk(req: ManualChunkRequest):
    if not req.text.strip():
        raise HTTPException(400, "text cannot be empty")
    if not req.label.strip():
        raise HTTPException(400, "label cannot be empty")

    chunk_id = f"manual:{_slugify(req.label)}:{int(time.time())}"
    chunk = Chunk(
        chunk_id=chunk_id,
        text=req.text,
        source_page=max(0, req.source_page),
        start_char=0,
        end_char=len(req.text),
        source_doc=req.source_doc,
        source_anchor=req.source_anchor or first_anchor(req.text),
    )
    # Manual chunks are concept nodes — label + selected text form the searchable attention anchor.
    embedding = embed_query(f"{req.label}\n{req.text}")
    meta = DocMeta(
        region=req.region,
        year=req.year,
        perspective=req.perspective,
        project_id=req.project_id,
    )
    get_store().upsert_manual(chunk, embedding, req.label, meta)

    return ManualChunkInfo(
        chunk_id=chunk_id,
        text=req.text,
        label=req.label,
        source_doc=req.source_doc,
        source_page=chunk.source_page,
        source_anchor=chunk.source_anchor,
        project_id=req.project_id,
        region=req.region,
        year=req.year,
        perspective=req.perspective,
    )


@app.get("/chunks/manual", response_model=list[ManualChunkInfo])
def list_manual_chunks(project_id: str = "default"):
    payloads = get_store().manual_chunks(project_id=project_id)
    return [
        ManualChunkInfo(
            chunk_id=p["chunk_id"],
            text=p["text"],
            label=p.get("label") or "",
            source_doc=p.get("source_doc") or "",
            source_page=int(p.get("source_page") or 0),
            source_anchor=p.get("source_anchor"),
            project_id=p.get("project_id") or "default",
            region=p.get("region"),
            year=p.get("year"),
            perspective=p.get("perspective"),
        )
        for p in payloads
    ]


@app.delete("/chunks/manual/{chunk_id}")
def delete_manual_chunk(chunk_id: str, project_id: str = "default"):
    store = get_store()
    removed_relation_ids = remove_relations_for_chunks({chunk_id}, project_id)
    store.remove_chunk(chunk_id)
    for relation_id in removed_relation_ids:
        store.remove_relation(relation_id)
    return {"status": "removed", "chunk_id": chunk_id}


# ── Chunk relations ───────────────────────────────────────────────────────────

@app.post("/chunks/relations", response_model=RelationInfo)
def create_relation(req: RelationRequest):
    label = req.label.strip()
    if not label:
        raise HTTPException(400, "label cannot be empty")
    if req.from_chunk_id == req.to_chunk_id:
        raise HTTPException(400, "from and to must be different chunks")
    normalized_label = label.casefold()
    duplicate = next(
        (
            rel
            for rel in list_relations(req.project_id)
            if rel.get("from_chunk_id") == req.from_chunk_id
            and rel.get("to_chunk_id") == req.to_chunk_id
            and str(rel.get("label", "")).strip().casefold() == normalized_label
        ),
        None,
    )
    if duplicate:
        raise HTTPException(409, "relation already exists for this source, target, and label")
    relation = add_relation(
        from_chunk_id=req.from_chunk_id,
        to_chunk_id=req.to_chunk_id,
        label=label,
        weight=max(0.0, min(1.0, req.weight)),
        project_id=req.project_id,
    )
    _upsert_relation_vector(relation)
    return RelationInfo(**relation)


@app.get("/chunks/relations", response_model=list[RelationInfo])
def get_relations(project_id: str = "default"):
    return [RelationInfo(**r) for r in list_relations(project_id)]


class RelationWeightUpdate(BaseModel):
    weight: float


@app.patch("/chunks/relations/{relation_id}/weight", response_model=RelationInfo)
def update_relation_weight_endpoint(relation_id: str, body: RelationWeightUpdate, project_id: str = "default"):
    ok = update_relation_weight(relation_id, body.weight, project_id)
    if not ok:
        raise HTTPException(404, f"Relation '{relation_id}' not found")
    get_store().set_relation_weight(relation_id, body.weight)
    relations = list_relations(project_id)
    r = next((x for x in relations if x["id"] == relation_id), None)
    if not r:
        raise HTTPException(404)
    return RelationInfo(**r)


@app.delete("/chunks/relations/{relation_id}")
def remove_relation_endpoint(relation_id: str, project_id: str = "default"):
    ok = delete_relation(relation_id, project_id)
    if not ok:
        raise HTTPException(404, f"Relation '{relation_id}' not found")
    get_store().remove_relation(relation_id)
    return {"status": "removed", "id": relation_id}


# ── Query ────────────────────────────────────────────────────────────────────

@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    store = get_store()
    if not store.is_ready_for_project(req.project_id):
        raise HTTPException(400, "No document indexed. Upload a PDF first.")

    retrieval = retrieve(req.question, store, top_k=req.top_k, region=req.region, year=req.year, project_id=req.project_id)
    results = retrieval.results

    # Build enriched relations once — reused for both answer generation and anomaly C2
    raw_relations = list_relations(req.project_id)
    manual_map = {p["chunk_id"]: p.get("text", "") for p in store.manual_chunks(project_id=req.project_id)}
    retrieved_map = {r.chunk.chunk_id: r.chunk.text for r in results}
    def _chunk_label(chunk_id: str) -> str:
        # manual chunk_ids look like "manual:致災:1777448602" — extract the label part
        parts = chunk_id.split(":")
        return parts[1] if len(parts) >= 3 and parts[0] == "manual" else chunk_id

    enriched_relations = [
        {
            "from_chunk_id": rel["from_chunk_id"],
            "to_chunk_id":   rel["to_chunk_id"],
            "label":         rel["label"],
            "weight":        rel.get("weight", 1.0),
            "from_label":    _chunk_label(rel["from_chunk_id"]),
            "to_label":      _chunk_label(rel["to_chunk_id"]),
            "from_text":     manual_map.get(rel["from_chunk_id"]) or retrieved_map.get(rel["from_chunk_id"], ""),
            "to_text":       manual_map.get(rel["to_chunk_id"])   or retrieved_map.get(rel["to_chunk_id"], ""),
        }
        for rel in raw_relations
    ]

    retrieved: list[RetrievedChunk] = []
    for r in results:
        payload = store.get_payload(r.chunk.chunk_id) or {}
        node_type = str(payload.get("node_type") or ("manual" if r.chunk.chunk_id.startswith("manual:") else "auto"))
        label = payload.get("label") or (_chunk_label(r.chunk.chunk_id) if r.is_boosted else None)
        retrieved.append(
            RetrievedChunk(
                chunk_id=r.chunk.chunk_id,
                text=r.chunk.text,
                source_page=r.chunk.source_page,
                score=r.score,
                source_doc=str(payload.get("source_doc") or r.chunk.source_doc or ""),
                source_anchor=payload.get("source_anchor") or r.chunk.source_anchor,
                label=str(label) if label else None,
                is_manual=bool(payload.get("is_manual", r.chunk.chunk_id.startswith("manual:"))),
                is_boosted=r.is_boosted,
                node_type=node_type,
                hazard_tags=list(payload.get("hazard_tags") or []),
            )
        )

    answer = generate_answer(req.question, results, relations=enriched_relations)

    graph = _build_graph(req.question, answer, retrieved, store, project_id=req.project_id)
    anomalies: list[AnomalyFlag] = []
    retrieved_payload = [chunk.model_dump() for chunk in retrieved]
    out_of_domain = detect_out_of_domain(
        retrieval.max_auto_score,
        question=req.question,
        retrieved=retrieved_payload,
    )
    if out_of_domain:
        anomalies.append(AnomalyFlag(type=out_of_domain.type, message=out_of_domain.message, details=out_of_domain.details))
    graph_out_of_domain = detect_graph_out_of_domain(
        req.question,
        retrieved_payload,
        retrieval.router,
    )
    if (
        graph_out_of_domain
        and not any(a.type == "out_of_domain" for a in anomalies)
        and not any(a.type == graph_out_of_domain.type for a in anomalies)
    ):
        anomalies.append(AnomalyFlag(
            type=graph_out_of_domain.type,
            message=graph_out_of_domain.message,
            details=graph_out_of_domain.details,
        ))
    contradiction = detect_relation_contradiction(req.question, enriched_relations)
    if contradiction:
        anomalies.append(AnomalyFlag(type=contradiction.type, message=contradiction.message, details=contradiction.details))

    response = QueryResponse(
        question=req.question,
        answer=answer,
        retrieved_chunks=retrieved,
        graph_data=graph,
        anomalies=anomalies,
        router=retrieval.router,
    )
    save_graph(req.project_id, "query_graph", response.graph_data.model_dump())
    return response


# ── UMAP ─────────────────────────────────────────────────────────────────────

@app.post("/umap", response_model=UMAPResponse)
def umap_projection(req: UMAPRequest):
    store = get_store()
    if not store.is_ready_for_project(req.project_id):
        raise HTTPException(400, "No document indexed.")

    chunks, embeddings = store.get_all(project_id=req.project_id)

    retrieved_map: dict[str, float] = {}
    query_vec = None

    if req.question:
        query_vec = embed_query(req.question)
        results = retrieve(req.question, store, top_k=req.top_k, region=req.region, year=req.year, project_id=req.project_id).results
        retrieved_map = {r.chunk.chunk_id: r.score for r in results}

    coords, query_coords = compute_umap(embeddings, query_vec)

    payload_map = store.payloads_by_chunk_id(project_id=req.project_id)
    manual_ids: set[str] = {
        chunk_id for chunk_id, payload in payload_map.items()
        if payload.get("is_manual") and payload.get("node_type") != "relation"
    }

    points = [
        UMAPPointModel(
            chunk_id=chunk.chunk_id,
            x=float(coords[i, 0]),
            y=float(coords[i, 1]),
            text=chunk.text[:300],
            source_page=chunk.source_page,
            source_doc=payload_map.get(chunk.chunk_id, {}).get("source_doc", chunk.source_doc),
            label=payload_map.get(chunk.chunk_id, {}).get("label"),
            node_type=payload_map.get(chunk.chunk_id, {}).get("node_type", "auto"),
            is_retrieved=chunk.chunk_id in retrieved_map,
            is_manual=chunk.chunk_id in manual_ids,
            score=retrieved_map.get(chunk.chunk_id, 0.0),
        )
        for i, chunk in enumerate(chunks)
    ]

    response = UMAPResponse(
        points=points,
        query_x=float(query_coords[0]) if query_coords is not None else None,
        query_y=float(query_coords[1]) if query_coords is not None else None,
        query_label=req.question[:40] if req.question else None,
    )
    save_graph(req.project_id, "embedding_space", response.model_dump())
    return response


# ── Graph JSON explorer ──────────────────────────────────────────────────────

@app.get("/graphs/json", response_model=GraphJsonListResponse)
def graph_json_list(project_id: str = "default"):
    return GraphJsonListResponse(files=[GraphJsonInfo(**item) for item in list_graphs(project_id)])


@app.get("/graphs/json/{filename}")
def graph_json_read(filename: str, project_id: str = "default"):
    try:
        return read_graph(project_id, filename)
    except FileNotFoundError:
        raise HTTPException(404, "Graph JSON not found.")


# ── Graph analysis ───────────────────────────────────────────────────────────

@app.post("/graph-analysis", response_model=GraphAnalysisResponse)
def graph_analysis(req: GraphAnalysisRequest):
    store = get_store()
    if not store.is_ready_for_project(req.project_id):
        raise HTTPException(400, "No document indexed.")

    chunks, embeddings = store.get_all(project_id=req.project_id)
    payload_map = store.payloads_by_chunk_id(project_id=req.project_id)

    retrieved_ids: set[str] = set()
    if req.question:
        results = retrieve(req.question, store, top_k=req.top_k, region=req.region, year=req.year, project_id=req.project_id).results
        retrieved_ids = {r.chunk.chunk_id for r in results}

    manual_ids: set[str] = {
        chunk_id
        for chunk_id, payload in payload_map.items()
        if payload.get("is_manual") and payload.get("node_type") != "relation"
    }

    raw_relations = list_relations(req.project_id)
    manual_pairs = [(r["from_chunk_id"], r["to_chunk_id"], float(r.get("weight", 1.0))) for r in raw_relations]

    result: GraphAnalysisResult = build_similarity_graph(
        chunks, embeddings, threshold=req.threshold,
        retrieved_ids=retrieved_ids, manual_relation_pairs=manual_pairs,
    )

    # Build label → chunk payload map for keyword extraction
    nodes = [
        GraphAnalysisNodeModel(
            id=n.id,
            label=payload_map.get(n.id, {}).get("label") or n.label,
            keywords=extract_keywords(
                n.text,
                label=payload_map.get(n.id, {}).get("label"),
            ),
            page=n.page,
            source_doc=payload_map.get(n.id, {}).get("source_doc", ""),
            node_type=payload_map.get(n.id, {}).get("node_type", "auto"),
            hazard_tags=payload_map.get(n.id, {}).get("hazard_tags", []),
            project_id=payload_map.get(n.id, {}).get("project_id", req.project_id),
            degree_centrality=n.degree_centrality,
            betweenness_centrality=n.betweenness_centrality,
            community=n.community,
            text=n.text,
            is_retrieved=n.id in retrieved_ids,
            is_manual=n.id in manual_ids,
        )
        for n in result.nodes
    ]
    edges = [
        GraphAnalysisEdgeModel(source=e.source, target=e.target, weight=e.weight)
        for e in result.edges
    ]

    relations = [RelationInfo(**r) for r in raw_relations]

    response = GraphAnalysisResponse(
        nodes=nodes,
        edges=edges,
        num_communities=result.num_communities,
        density=result.density,
        manual_relations=relations,
    )
    save_graph(req.project_id, "graph_analysis", response.model_dump())
    save_graph(req.project_id, "knowledge_graph", _knowledge_graph_export(response))
    return response


def _knowledge_graph_export(response: GraphAnalysisResponse) -> dict:
    node_ids = {
        node.id for node in response.nodes
        if node.node_type != "relation" and (node.is_manual or node.node_type == "manual")
    }
    relation_node_ids = {
        rel.from_chunk_id for rel in response.manual_relations
    } | {
        rel.to_chunk_id for rel in response.manual_relations
    }
    if relation_node_ids:
        node_ids |= relation_node_ids

    nodes = [
        node.model_dump()
        for node in response.nodes
        if node.id in node_ids
    ]
    relations = [
        rel.model_dump()
        for rel in response.manual_relations
        if rel.from_chunk_id in node_ids and rel.to_chunk_id in node_ids
    ]
    return {
        "nodes": nodes,
        "relations": relations,
        "node_count": len(nodes),
        "relation_count": len(relations),
    }


# ── Graph builder helper ─────────────────────────────────────────────────────

def _build_graph(
    question: str,
    answer: str,
    retrieved: list[RetrievedChunk],
    store: QdrantStore,
    project_id: str = "default",
) -> GraphData:
    doc_names = store.docs(project_id=project_id)

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    for doc in doc_names:
        nodes.append(GraphNode(id=f"pdf_{doc}", label=doc, type="pdf", active=True))
        edges.append(GraphEdge(source=f"pdf_{doc}", target="faiss", label="chunk+embed", active=True))

    nodes += [
        GraphNode(id="faiss", label="Qdrant", type="faiss", active=True),
        GraphNode(
            id="query",
            label=f"Query\n{question[:40]}…" if len(question) > 40 else f"Query\n{question}",
            type="query",
            active=True,
        ),
        GraphNode(id="llm", label="Claude LLM", type="llm", active=True),
        GraphNode(id="answer", label="Answer", type="answer", active=True, data={"text": answer}),
    ]
    edges += [
        GraphEdge(source="query", target="faiss", label="embed+search", active=True),
        GraphEdge(source="faiss", target="llm", label="top-k context", active=True),
        GraphEdge(source="llm", target="answer", label="generate", active=True),
    ]

    active_ids = {r.chunk_id for r in retrieved}
    for r in retrieved:
        nid = f"chunk_{r.chunk_id}"
        nodes.append(
            GraphNode(
                id=nid,
                label=f"{r.chunk_id}\np{r.source_page} | {r.score:.2f}",
                type="chunk",
                active=True,
                data={"text": r.text, "score": r.score, "page": r.source_page},
            )
        )
        edges.append(GraphEdge(source="faiss", target=nid, label=f"{r.score:.2f}", active=True))
        edges.append(GraphEdge(source=nid, target="llm", active=True))

    chunks, _ = store.get_all(project_id=project_id)
    shown = 0
    for c in chunks:
        if shown >= 20 or c.chunk_id in active_ids:
            continue
        pdf_id = f"pdf_{c.source_doc}" if c.source_doc and c.source_doc in doc_names else "faiss"
        nodes.append(
            GraphNode(
                id=f"chunk_{c.chunk_id}",
                label=f"{c.chunk_id}\np{c.source_page}",
                type="chunk",
                active=False,
                data={"text": c.text, "page": c.source_page},
            )
        )
        edges.append(GraphEdge(source=pdf_id, target=f"chunk_{c.chunk_id}", active=False))
        shown += 1

    return GraphData(nodes=nodes, edges=edges)


def _chunk_label_from_payload(payload: dict | None, fallback: str) -> str:
    if not payload:
        return fallback
    return payload.get("label") or (payload.get("text") or fallback)[:40] or fallback


def _upsert_relation_vector(relation: dict) -> None:
    store = get_store()
    from_payload = store.get_payload(relation["from_chunk_id"])
    to_payload = store.get_payload(relation["to_chunk_id"])
    from_label = _chunk_label_from_payload(from_payload, relation["from_chunk_id"])
    to_label = _chunk_label_from_payload(to_payload, relation["to_chunk_id"])
    relation_text = (
        f"關係節點：{from_label} --{relation['label']}--> {to_label}\n"
        f"來源內容：{(from_payload or {}).get('text', '')[:500]}\n"
        f"目標內容：{(to_payload or {}).get('text', '')[:500]}\n"
        f"關係權重：{float(relation.get('weight', 1.0)):.2f}"
    )
    store.upsert_relation(
        relation_id=relation["id"],
        embedding=embed_query(relation_text),
        text=relation_text,
        label=relation["label"],
        from_chunk_id=relation["from_chunk_id"],
        to_chunk_id=relation["to_chunk_id"],
        weight=float(relation.get("weight", 1.0)),
        project_id=relation["project_id"],
    )
