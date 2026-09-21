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
| VLM parsing | Local Ollama `gemma4:12b-it-q4_K_M` |
| LLM answer generation | Local Ollama `gemma4:12b-it-q4_K_M` |
| Vector DB | Qdrant |
| Metadata DB | PostgreSQL 16 |
| Graph analysis | NetworkX |
| Graph UI | Cytoscape.js |
| Embedding projection | UMAP |
| Embeddings | Ollama `nomic-embed-text` by default |

## Quick Start

### 1. Start storage services

```bash
docker compose up -d postgres qdrant
```

Default local ports:

- PostgreSQL: `localhost:55432`
- Qdrant: `localhost:6333`

### 2. Configure local environment

The one-command startup creates the database secret, builds the frontend, and serves the UI and API from one intranet port. Authentication is disabled by default for trusted intranet testing. First install the required local models:

```bash
ollama pull gemma4:12b-it-q4_K_M
ollama pull nomic-embed-text
./start.sh
```

For manual startup, copy `.env.example` and `backend/.env.example` to their corresponding `.env` files. Set `APP_PORT` in the root `.env` to the single port that operations will allow from the intranet.

Useful defaults in `backend/.env.example`:

```bash
DATABASE_URL=postgresql://visual_rag:<local-password>@localhost:55432/visual_rag
RAG_AUTH_ENABLED=0
QDRANT_URL=http://localhost:6333
OLLAMA_URL=http://localhost:11434
EMBED_MODEL=nomic-embed-text
OLLAMA_MODEL=gemma4:12b-it-q4_K_M
```

For maintainer handoff, keep `DATABASE_URL` and `QDRANT_URL` enabled. Do not set `QDRANT_PATH` in production unless you intentionally want local file-mode vector storage.

## Vendor Environment Checklist

When handing the system to an operations vendor, ask them to create `backend/.env` from `backend/.env.example` and fill the values below.

### Required

| Key | What To Fill | Example / Note |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | Use the password from the root `.env` |
| `RAG_AUTH_ENABLED` | Enable API-key authentication | `0` for the current trusted-intranet deployment |
| `QDRANT_URL` | Qdrant server URL | `http://localhost:6333` |
| `OLLAMA_URL` | Local Ollama server URL | `http://localhost:11434` |
| `EMBED_MODEL` | Ollama embedding model | `nomic-embed-text` |
| `OLLAMA_MODEL` | Local text and vision model | `gemma4:12b-it-q4_K_M` |
| `DSM_API_BASE_URL` | Vendor DSM API host and port, required for external image-recognition nodes | `http://localhost:3000` |
| `DSM_API_TIMEOUT` | DSM API timeout in seconds | `8` |

### Required Local Service Setup

```bash
docker compose up -d postgres qdrant
ollama pull gemma4:12b-it-q4_K_M
ollama pull nomic-embed-text
```

The vendor should verify:

```bash
curl http://127.0.0.1:8000/api/health
curl http://localhost:6333/collections
curl http://localhost:11434/api/tags
```

### Optional / Tuning

| Key | Purpose | Suggested Default |
|---|---|---|
| `VLM_MAX_PAGES` | Maximum PDF pages parsed by VLM | `20` |
| `VLM_RENDER_DPI` | PDF page render resolution before VLM parsing | `160` |
| `VLM_CONCURRENCY` | Number of pages processed in parallel | `4` |
| `VLM_TIMEOUT` | VLM request timeout in seconds | `120` to `180` |
| `VLM_CACHE` | Reuse VLM page parsing cache | `1` |
| `CHUNK_MODE` | Knowledge-node preprocessing mode | `semantic` |
| `TOP_K` | Retrieval evidence count | `5` |
| `SEMANTIC_THRESHOLD` | Semantic split threshold | `0.70` for clean production; lower only for testing |
| `MANUAL_BOOST` | Boost reviewed knowledge nodes during retrieval | `0.15` |
| `DSM_API_BASE_URL` | Vendor DSM image-recognition API base URL | `http://localhost:3000` |
| `DSM_API_TIMEOUT` | Timeout for DSM API reads, in seconds | `8` |

## Vendor DSM API Integration

The left project form has **Location** and **Date** dropdowns. These dropdowns are also the bridge to the vendor DSM image-recognition system.

When a user creates a project:

1. The frontend sends the selected location/date to this system.
2. The backend reads matching DSM metadata from `backend/config/project_filter_options.json`.
3. If the metadata contains a DSM result JSON path, the backend calls the vendor API at `DSM_API_BASE_URL`.
4. The DSM result JSON is converted into `external_vision` knowledge nodes.
5. These nodes are written to PostgreSQL and Qdrant, then displayed in the knowledge graph with a distinct DSM color.

### Vendor Responsibilities

The operations vendor should provide or confirm:

| Item | Required Value |
|---|---|
| DSM API base URL | Example: `http://localhost:3000` |
| Result JSON endpoint path | Example: `/api/dsm-images/results/19_result.json` |
| Result image endpoint path, optional | Example: `/api/dsm-images/results/19_result.jpg` |
| JSON schema for detections | Prefer keys like `detections`, `objects`, `instances`, `results`, `items`, or `features` |
| Class labels | Example: `fall`, `normal` |
| Confidence field, optional | Example: `confidence`, `score`, or `probability` |
| Bounding box / geometry field, optional | Example: `bbox`, `box`, `bounds`, `centroid`, or `area` |

### Backend Environment

Add these values to `backend/.env`:

```bash
DSM_API_BASE_URL=http://localhost:3000
EXTERNAL_VISION_API_URL=http://localhost:3000
DSM_API_TIMEOUT=8
```

`DSM_API_BASE_URL` is the primary setting. `EXTERNAL_VISION_API_URL` is kept as an alias for future non-DSM image-recognition services. These values are intentionally not hard-coded in the frontend. If the vendor changes the DSM port or host, update only the backend env file.

### Dropdown Metadata Mapping

Each location/date option can include DSM metadata in `backend/config/project_filter_options.json`.

Example:

```json
{
  "value": "台2線70.1K 平浪橋南側",
  "label": "台2線70.1K 平浪橋南側",
  "metadata": {
    "source": "geoport",
    "node_source": "external_reference",
    "dsm_job_id": 19,
    "dsm_result_json_path": "/api/dsm-images/results/19_result.json",
    "dsm_result_image_path": "/api/dsm-images/results/19_result.jpg"
  }
}
```

The backend currently accepts any of these JSON path keys:

- `dsm_result_json_path`
- `outputJsonPath`
- `output_json_path`
- `resultJsonPath`

It also accepts filename-only metadata:

```json
{
  "outputJsonFilename": "19_result.json"
}
```

This resolves to:

```text
/api/dsm-images/results/19_result.json
```

### DSM API Endpoints Used By This System

This system only needs to read the finished DSM result JSON for project creation:

| Method | Endpoint | Used For |
|---|---|---|
| `GET` | `/api/dsm-images/results/:filename` | Read finished DSM result JSON |

The vendor may still operate the full DSM workflow separately:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/dsm` | List DSM files |
| `GET` | `/api/dsm/:id` | Get one DSM file |
| `POST` | `/api/dsm/upload` | Upload DSM file |
| `POST` | `/api/dsm/start-detect/:id` | Start recognition |
| `GET` | `/api/dsm/jobs/:jobId` | Read job status |
| `GET` | `/api/dsm/jobs/pending` | List pending jobs |

### Preview Endpoint In This System

The frontend calls this API before project creation to show whether DSM data is available:

```bash
GET /external/dsm/preview?location=台2線70.1K%20平浪橋南側&date=2024-06-03
```

Response shape:

```json
{
  "available": true,
  "message": "已讀取 2 筆 DSM 影像辨識資料",
  "source_url": "http://localhost:3000/api/dsm-images/results/19_result.json",
  "records": [
    {
      "id": "dsm:1",
      "label": "DSM影像辨識_fall_1",
      "text": "DSM 影像辨識外部資料...",
      "class_name": "fall",
      "confidence": 0.91
    }
  ]
}
```

### Do Not Use In Production

```bash
QDRANT_PATH=./qdrant_data
```

`QDRANT_PATH` is only for local file-mode testing. In vendor handoff, keep it commented out and use `QDRANT_URL` so vectors are stored in the Qdrant service.

### 3. Start backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

App and API: `http://<server-ip>:8000` and `http://<server-ip>:8000/api`

Only `APP_PORT` (default `8000`) should be opened to the intranet. Keep ports `55432`, `6333`, `6334`, and `11434` host-local.

### One-command local startup

```bash
./start.sh
```

The script creates the database secret, starts PostgreSQL and Qdrant, builds the frontend, and serves the complete application from `0.0.0.0:${APP_PORT:-8000}`. It stops with the exact `ollama pull` command when a required local model is missing.

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
