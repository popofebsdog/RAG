# Visual RAG System

An **Explainable RAG** system that shows not just the answer, but the full pipeline — why the answer was generated and where the information came from.

## Features

- **PDF Ingestion** — Upload any PDF; extracted, chunked, and embedded automatically
- **Qdrant Vector Search** — Persistent cosine similarity retrieval
- **PostgreSQL Metadata Store** — Production storage for projects, documents, nodes, relations, graph exports, and query logs
- **Claude LLM** — Answers grounded strictly in document context
- **D3.js Pipeline Graph** — Interactive visualization of the full RAG flow
- **Chunk Highlighting** — See exactly which chunks were retrieved and their similarity scores

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.11 + FastAPI |
| Embeddings | `sentence-transformers` (all-MiniLM-L6-v2) |
| Metadata DB | PostgreSQL 16 |
| Vector DB | Qdrant |
| PDF Parsing | PyMuPDF (default) / Chandra OCR (optional) |
| LLM | Anthropic Claude claude-sonnet-4-6 |
| Frontend | Vue 3 + TypeScript + Vite |
| Graph | D3.js force simulation |
| Styling | Tailwind CSS |

## Quick Start

### 1. Backend

```bash
docker compose up -d postgres qdrant

cd backend
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=<your-anthropic-key>
# DATABASE_URL defaults to postgresql://visual_rag:visual_rag_password@localhost:55432/visual_rag
# QDRANT_URL defaults to http://localhost:6333

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

uvicorn main:app --reload
# API at http://localhost:8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# App at http://localhost:5173
```

### 3. Use it

1. Open `http://localhost:5173`
2. Drop a PDF into the upload panel
3. Wait for indexing (chunks + embeddings + Qdrant + PostgreSQL metadata)
4. Type a question → see the answer + graph visualization

## Optional: Chandra OCR for scanned PDFs

For scanned documents with complex tables/forms, set `PDF_LOADER=chandra` in `.env`.

```bash
pip install chandra-ocr
# Requires a running vLLM server or HuggingFace model
# See https://github.com/datalab-to/chandra
```

## Project Structure

```
visual-rag-system/
├── backend/
│   ├── main.py              # FastAPI app + endpoints
│   ├── rag/
│   │   ├── loader.py        # PDF → pages (PyMuPDF / Chandra)
│   │   ├── chunking.py      # Pages → overlapping chunks
│   │   ├── embedding.py     # Chunks → sentence-transformer vectors
│   │   ├── qdrant_store.py  # Qdrant vector storage
│   │   ├── postgres_store.py # PostgreSQL schema + metadata storage
│   │   ├── retrieval.py     # Query → top-k chunks
│   │   └── llm.py           # Chunks + query → Claude answer
│   └── requirements.txt
└── frontend/
    └── src/
        ├── components/
        │   ├── GraphView/   # D3.js force graph
        │   ├── ChatPanel/   # Q&A interface
        │   └── UploadPanel/ # PDF drag-and-drop
        ├── composables/useRag.ts   # API calls
        └── types/rag.ts            # Shared TypeScript types
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Status + indexed chunk count |
| GET | `/project/filter-options` | Project location/date dropdown JSON source |
| POST | `/projects/upsert` | Persist project metadata to PostgreSQL |
| POST | `/ingest` | Upload PDF → build PostgreSQL metadata + Qdrant vectors |
| POST | `/query` | Question → answer + graph data |

## Production Storage Model

- PostgreSQL is the source of truth for structured metadata: projects, documents, chunks/nodes, relations, graph export metadata, and query/anomaly logs.
- Qdrant is the vector database for text chunks, manual nodes, relation vectors, and image embeddings.
- PDF originals, rendered pages, OCR/VLM cache, and graph JSON files remain file/object-storage assets. For cloud deployment, mount these folders to persistent storage or object storage.
