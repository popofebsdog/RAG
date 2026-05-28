# Visual RAG System

Visual RAG System is a maintainable GraphRAG prototype for disaster and engineering PDF reports.

The system turns technical PDF content into editable knowledge nodes, node relations, vector indexes, and an interactive knowledge graph. It is designed for reports where key evidence may be inside text, tables, figures, maps, and annotated images.

## What This Version Does

- **VLM PDF understanding**: PDF pages are rendered and interpreted by a vision-language model so image-heavy reports can be converted into structured knowledge.
- **Human-in-the-loop knowledge node review**: uploaded PDFs first produce candidate knowledge nodes. Users can approve or edit them before the knowledge graph is created.
- **Knowledge graph editing**: users can inspect knowledge nodes, create or adjust node relations, and write relation vectors back into the vector store.
- **Query-aware graph visualization**: questions appear as temporary query nodes on the graph. In-domain questions connect to matched knowledge nodes; out-of-domain questions show as red warning nodes.
- **Anomaly warning layer**: out-of-domain questions and weakly supported questions are surfaced visually without polluting the knowledge graph.
- **Original PDF grounding**: knowledge nodes retain source document and page metadata so users can inspect the original PDF context.
- **Project isolation**: each project keeps separate PDFs, knowledge nodes, node relations, graph JSON, and query logs.
- **Graph JSON explorer**: generated graph JSON files can be browsed from the UI.
- **Production-oriented storage**: PostgreSQL stores structured metadata; Qdrant stores vector embeddings.

## Current Workflow

```mermaid
flowchart LR
  A["Create / select project"] --> B["Upload PDF"]
  B --> C["VLM parses PDF pages"]
  C --> D["Candidate knowledge nodes"]
  D --> E["User reviews / edits nodes"]
  E --> F["Commit to PostgreSQL + Qdrant"]
  F --> G["Build knowledge graph"]
  G --> H["Edit node relations"]
  G --> I["Ask questions"]
  I --> J["Query node + highlighted evidence"]
  I --> K["Out-of-domain warning when needed"]
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python + FastAPI |
| Frontend | Vue 3 + TypeScript + Vite |
| PDF rendering | PyMuPDF |
| VLM parsing | Anthropic Claude Vision or OpenAI Vision-compatible model |
| LLM answer generation | Anthropic Claude by default |
| Vector DB | Qdrant |
| Metadata DB | PostgreSQL 16 |
| Graph analysis | NetworkX |
| Graph UI | Cytoscape.js |
| Embedding projection | UMAP |
| Embeddings | `sentence-transformers` by default |

## Quick Start

### 1. Start storage services

```bash
docker compose up -d postgres qdrant
```

Default local ports:

- PostgreSQL: `localhost:55432`
- Qdrant: `localhost:6333`

### 2. Configure backend environment

```bash
cd backend
cp .env.example .env
```

Set at least one API key:

```bash
ANTHROPIC_API_KEY=<your-anthropic-key>
# or
OPENAI_API_KEY=<your-openai-key>
```

Useful defaults in `backend/.env.example`:

```bash
DATABASE_URL=postgresql://visual_rag:visual_rag_password@localhost:55432/visual_rag
QDRANT_URL=http://localhost:6333
VLM_PROVIDER=anthropic
ANTHROPIC_VISION_MODEL=claude-sonnet-4-5
OPENAI_VISION_MODEL=gpt-4.1-mini
```

### 3. Start backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

API: `http://127.0.0.1:8000`

### 4. Start frontend

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

App: `http://127.0.0.1:5173`

### One-command local startup

```bash
./start.sh
```

The script starts PostgreSQL, Qdrant, backend, and frontend. If `backend/.env` does not exist, it creates one and asks you to set the API key.

## How To Use

1. Create or select a project from the left workspace.
2. Upload a PDF.
3. Wait for VLM parsing.
4. Review the candidate knowledge nodes.
5. Confirm to build the knowledge graph.
6. Use **Knowledge Graph Edit** to inspect nodes and adjust node relations.
7. Ask questions in the right panel.
8. Check the temporary query node and highlighted evidence on the graph.

Important behavior:

- Closing the review dialog only hides it. The pending review remains available from the left upload panel.
- Pressing **Discard** removes the pending VLM review.
- Query nodes are temporary UI state. They are not written into PostgreSQL, Qdrant, or graph JSON.
- Out-of-domain questions do not highlight knowledge nodes as evidence.

## Core Concepts

| Term | Meaning |
|---|---|
| Knowledge node | A reviewed unit of knowledge extracted from PDF text or visual content. |
| Node relation | A directed relation between two knowledge nodes, such as `causes`, `located_at`, `observed_at`, or `supports`. |
| Knowledge graph | The project-level graph built from knowledge nodes and node relations. |
| Query node | A temporary visual node representing the latest question. |
| Warning node | A temporary red node for out-of-domain or unsupported questions. |

## API Overview

### Project and files

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service status |
| `GET` | `/project/filter-options` | Dropdown sources for project metadata |
| `POST` | `/projects/upsert` | Save project metadata |
| `GET` | `/project/files` | List project PDFs |
| `DELETE` | `/project/clear` | Clear all project data |
| `DELETE` | `/project/files/{filename}` | Delete one PDF and its derived data |
| `GET` | `/project/files/{filename}/pdf` | Serve original PDF |
| `GET` | `/project/files/{filename}/info` | PDF metadata |
| `GET` | `/project/files/{filename}/page-image/{page_num}.png` | Rendered PDF page image |

### VLM ingest and review

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/ingest/preview` | Upload PDF and produce candidate knowledge nodes |
| `POST` | `/ingest/commit` | Commit reviewed nodes and relations |
| `POST` | `/ingest` | Legacy direct ingest endpoint |
| `POST` | `/vlm/selection` | Interpret a user-selected PDF image region |

### Knowledge nodes and node relations

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/chunks/manual` | List reviewed/user-created knowledge nodes |
| `POST` | `/chunks/manual` | Create a knowledge node |
| `DELETE` | `/chunks/manual/{chunk_id}` | Delete a knowledge node |
| `GET` | `/chunks/relations` | List node relations |
| `POST` | `/chunks/relations` | Create a node relation |
| `PATCH` | `/chunks/relations/{relation_id}/weight` | Update relation weight |
| `DELETE` | `/chunks/relations/{relation_id}` | Delete a node relation |

The API still uses `chunk` in some endpoint names for backward compatibility. The UI uses the user-facing term **knowledge node**.

### Query and visualization

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/query` | Ask a question and return answer, retrieval evidence, and warnings |
| `POST` | `/graph-analysis` | Build graph analysis view |
| `POST` | `/umap` | Build embedding projection |
| `GET` | `/graphs/json` | List exported graph JSON files |
| `GET` | `/graphs/json/{filename}` | Read one graph JSON file |

## Storage Model

### PostgreSQL

Stores maintainable structured metadata:

- projects
- PDF document metadata
- knowledge node records
- node relation records
- graph export metadata
- query logs and anomaly logs

### Qdrant

Stores vectorized retrieval objects:

- reviewed knowledge nodes
- node relations
- image-derived or selection-derived knowledge

### File storage

Local folders store binary and generated assets:

- original PDFs
- rendered page images
- OCR/VLM cache
- graph JSON output

For production deployment, mount these folders to persistent storage or replace them with object storage.

## Repository Structure

```text
visual-rag-system/
├── backend/
│   ├── main.py
│   ├── rag/
│   │   ├── loader.py
│   │   ├── knowledge_extraction.py
│   │   ├── standardization.py
│   │   ├── qdrant_store.py
│   │   ├── postgres_store.py
│   │   ├── retrieval.py
│   │   ├── anomaly.py
│   │   └── llm.py
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── NodeReviewPanel/
│       │   ├── GraphAnalysisView/
│       │   ├── KnowledgeGraphView/
│       │   ├── GraphJsonExplorer/
│       │   ├── DocumentReader/
│       │   ├── UploadPanel/
│       │   └── ChatPanel/
│       ├── composables/useRag.ts
│       └── types/rag.ts
├── docker-compose.yml
└── start.sh
```

## Validation Commands

```bash
cd backend
python3 -m py_compile main.py rag/*.py

cd ../frontend
npm run build
```

## Current Scope

This project is a practical maintainable prototype, not a fully managed SaaS platform. It already separates project data and supports PostgreSQL + Qdrant, but production deployment should still add:

- authentication and authorization
- managed object storage for PDFs and page images
- backup and migration strategy
- request queueing for slow VLM parsing jobs
- structured observability and error reporting
