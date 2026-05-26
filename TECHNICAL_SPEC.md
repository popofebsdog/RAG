# Visual RAG System 技術說明書

更新日期：2026-05-20

## 1. 系統定位

本系統是一套面向災害調查報告的 Visual GraphRAG 原型，核心目標是將 PDF 報告轉換為可查詢、可視化、可編輯、可追溯的知識圖譜與向量資料庫。

目前系統重點不是訓練模型，而是透過：

- PDF / VLM 解析
- 結構化 Markdown 與 anchor
- 自動知識節點與關係抽取
- 使用者可編輯 node / relation
- Qdrant 向量檢索
- graph analysis / knowledge graph / graph JSON 輸出
- 異常警示

來形成可驗收的 RAG 資料庫與可視化流程。

## 2. 目前狀態評估

目前功能已達到可進入驗收測試的階段：

- PDF 可上傳、解析、入庫。
- VLM 可讀取投影片/圖像型報告內容。
- 系統可自動建立知識節點與 relation。
- 使用者可在圖分析與編輯介面調整 relation。
- 手動/自動節點已統一進入向量資料庫。
- 專案間資料已分離。
- graph analysis 與 knowledge graph 已可輸出 JSON。
- Graph JSON Explorer 已可列出與檢視目前專案的 graph JSON。
- 問答區已移除低價值的 score 與 retrieved chunk 細節。
- 異常警示目前分為：
  - `out_of_domain`：主題外問題
  - `insufficient_evidence`：缺少明確佐證
  - `relation_contradiction`：因果矛盾

暫時不建議新增「工程判讀 / 審查意見」回答模式，原因是目前資料量偏少，若加入角色 prompt 容易造成回答發散。現階段應優先維持問答穩定、圖譜可追溯、JSON 可驗收。

## 3. 技術架構

### 3.1 前端

- Framework：Vue 3
- Language：TypeScript
- Build tool：Vite
- Dev server：http://127.0.0.1:5173
- API proxy：`/api` 轉發至 `http://localhost:8000`

主要前端模組：

| 模組 | 路徑 | 說明 |
|---|---|---|
| App shell | `frontend/src/App.vue` | 主版面、左側工具列、問答區、原文區 |
| API composable | `frontend/src/composables/useRag.ts` | 前端 API 呼叫集中管理 |
| ChatPanel | `frontend/src/components/ChatPanel/ChatPanel.vue` | 問答介面 |
| DocumentReader | `frontend/src/components/DocumentReader/DocumentReader.vue` | PDF 原文、框選 VLM chunk |
| GraphAnalysisView | `frontend/src/components/GraphAnalysisView/GraphAnalysisView.vue` | 圖分析與 relation 編輯 |
| KnowledgeGraphView | `frontend/src/components/KnowledgeGraphView/KnowledgeGraphView.vue` | 知識圖譜檢視與 PDF 單頁對照 |
| GraphJsonExplorer | `frontend/src/components/GraphJsonExplorer/GraphJsonExplorer.vue` | 類 Swagger 的 graph JSON 檢視 |
| ProjectPanel | `frontend/src/components/ProjectPanel/ProjectPanel.vue` | 專案切換與建立 |
| UploadPanel | `frontend/src/components/UploadPanel/UploadPanel.vue` | PDF 上傳 |

### 3.2 後端

- Framework：FastAPI
- Language：Python 3.11
- API server：http://127.0.0.1:8000
- Main app：`backend/main.py`

主要後端模組：

| 模組 | 路徑 | 說明 |
|---|---|---|
| FastAPI app | `backend/main.py` | API endpoint 與主要流程 |
| PDF loader | `backend/rag/loader.py` | PyMuPDF / VLM 解析 |
| Chunking | `backend/rag/chunking.py` | 文章切分 |
| Markdown store | `backend/rag/markdown_store.py` | Markdown 與 anchor 儲存 |
| Page store | `backend/rag/page_store.py` | 頁面文字快取 |
| OCR store | `backend/rag/ocr_store.py` | OCR 結果快取 |
| Qdrant store | `backend/rag/qdrant_store.py` | 向量資料庫與 payload |
| Retrieval | `backend/rag/retrieval.py` | 查詢檢索、relation 擴展、source page context |
| Knowledge extraction | `backend/rag/knowledge_extraction.py` | 節點與關係抽取 |
| Graph analysis | `backend/rag/graph_analysis.py` | 相似度圖與 centrality/community |
| Graph JSON store | `backend/rag/graph_store.py` | graph JSON 輸出與讀取 |
| Anomaly | `backend/rag/anomaly.py` | 主題外、缺少佐證、因果矛盾判斷 |
| LLM answer | `backend/rag/llm.py` | 問答 LLM 呼叫 |

### 3.3 儲存層

| 類型 | 位置 | 說明 |
|---|---|---|
| 原始 PDF | `backend/source_cache/{project_id}/` | 原始檔案 |
| Page text | `backend/pages_cache/{project_id}/` | PDF 解析後頁面文字 JSON |
| Markdown | `backend/markdown_cache/{project_id}/` | 清理後 Markdown |
| Anchors | `backend/markdown_cache/{project_id}/*.anchors.json` | 段落 anchor |
| Images | `backend/images_cache/{project_id}/` | 頁面圖片 |
| OCR | `backend/ocr_cache/{project_id}/` | OCR 文字位置 |
| Relations | `backend/relations_cache/{project_id}/relations.json` | 使用者與自動 relation |
| Graph JSON | `backend/graphs_cache/{project_id}/` | graph JSON latest 檔 |
| Vector DB | `backend/qdrant_data/` | Qdrant local storage |

## 4. 資料流程

### 4.1 PDF 入庫流程

```text
PDF upload
  -> PDF loader / VLM parser
  -> page text
  -> clean Markdown + anchors
  -> semantic chunks
  -> embeddings
  -> Qdrant upsert
  -> extract knowledge graph
  -> manual-like knowledge nodes
  -> relation vectorization
```

### 4.2 問答流程

```text
question
  -> embed query
  -> Qdrant search
  -> hazard router score
  -> manual relation neighbor expansion
  -> source page context expansion
  -> LLM answer
  -> anomaly checks
  -> query graph JSON export
```

### 4.3 圖分析流程

```text
chunks + embeddings + relations
  -> similarity graph
  -> centrality / community / density
  -> graph-analysis view
  -> knowledge-graph projection
  -> graph JSON export
```

## 5. LLM 與模型設定

### 5.1 目前問答 LLM

問答回答目前由 `backend/rag/llm.py` 控制。

目前預設：

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
```

若 `.env` 未設定 `LLM_PROVIDER`，問答會走本機 Ollama：

```text
http://localhost:11434/api/chat
```

若要改為 API，需設定：

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-sonnet-4-5
```

目前尚未實作 OpenAI text answer provider；OpenAI 目前主要用於 VLM。

### 5.2 目前 VLM

`.env` 目前支援：

```env
VLM_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_VISION_MODEL=gpt-4.1-mini
```

VLM 用於：

- PDF 頁面圖像解析
- 原文區框選圖片後生成可編輯 chunk

### 5.3 Embedding

Embedding 由 `backend/rag/embedding.py` 控制。實際行為依 `.env` 與本機 Ollama embedding endpoint 決定。

## 6. Graph JSON 輸出

Graph JSON 會輸出至：

```text
backend/graphs_cache/{project_id}/
```

同時，graph export 的 metadata 會寫入 PostgreSQL `graph_exports`，包含 graph name、檔名、node count、edge count 與更新時間。完整 JSON 仍保留為檔案，避免大型 graph blob 造成資料庫膨脹。

## 7. 正式維運資料庫架構

本系統採用 PostgreSQL + Qdrant 混合式架構：

| 資料類型 | 儲存位置 | 說明 |
|---|---|---|
| Project / Document metadata | PostgreSQL | 專案、文件、頁數、chunk 數、區域、年份、視角 |
| Chunk / Node metadata | PostgreSQL | chunk id、label、text、source page、source doc、node type、hazard tags |
| Relation | PostgreSQL | from/to chunk、label、weight、vectorized 狀態；具唯一索引防重複 |
| Query / anomaly log | PostgreSQL | 問題、回答、router、retrieved chunks、anomalies |
| Text / relation / image vectors | Qdrant | similarity retrieval 與 embedding space |
| PDF 原檔與 VLM/OCR 中間產物 | 檔案系統 / Object Storage | 不放入 PostgreSQL，正式環境需掛載持久化 volume |

啟動時 FastAPI 會依 `DATABASE_URL` 自動初始化 PostgreSQL schema。若未設定 `DATABASE_URL`，系統會保留本機 JSON fallback，方便 demo；正式維運環境應一律設定 `DATABASE_URL`。

核心環境變數：

```env
DATABASE_URL=postgresql://visual_rag:visual_rag_password@localhost:55432/visual_rag
QDRANT_URL=http://localhost:6333
```

目前支援以下 latest 檔：

| 檔名 | 產生時機 | 說明 |
|---|---|---|
| `graph_analysis_latest.json` | 呼叫 `/graph-analysis` | 完整圖分析資料 |
| `knowledge_graph_latest.json` | 呼叫 `/graph-analysis` | 知識圖譜節點與 relation |
| `query_graph_latest.json` | 呼叫 `/query` | 問答流程圖 |
| `embedding_space_latest.json` | 呼叫 `/umap` | embedding 空間投影 |

Graph JSON Explorer 使用：

```text
GET /api/graphs/json?project_id={project_id}
GET /api/graphs/json/{filename}?project_id={project_id}
```

## 7. API 端點總覽

前端使用 `/api` proxy。以下端點以後端實際路徑表示，例如前端呼叫 `/api/health` 對應後端 `/health`。

### 7.1 Health

#### GET `/health`

用途：檢查後端狀態與已索引 chunk 數。

Response：

```json
{
  "status": "ok",
  "indexed_chunks": 0
}
```

### 7.2 Ingest

#### POST `/ingest`

用途：上傳 PDF 並建立 chunks、向量、knowledge nodes、relations。

Content-Type：`multipart/form-data`

Form fields：

| 欄位 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `file` | file | required | PDF 檔 |
| `loader_type` | string | `pymupdf4llm` | PDF loader |
| `chunk_mode` | string | `semantic` | chunk 模式 |
| `mode` | string | `append` | `append` 或 `replace` |
| `chunk_strategy` | string | `auto` | 保留欄位，目前主要走 unified flow |
| `project_id` | string | `default` | 專案 ID |
| `region` | string | empty | 地區 metadata |
| `year` | string | empty | 年份 metadata |
| `date` | string | empty | 日期 metadata，來自專案篩選下拉選單 |
| `perspective` | string | empty | 視角 metadata |

Response：`IngestResponse`

```json
{
  "filename": "report.pdf",
  "total_pages": 3,
  "total_chunks": 21,
  "chunks": []
}
```

### 7.3 Project and Files

#### GET `/project/filter-options`

用途：取得建立專案時的地點、日期與視角下拉選項。現階段由 `backend/config/project_filter_options.json` 提供，之後可替換為外部 API 回傳 JSON。

Response：

```json
{
  "locations": [{ "value": "台2線70.1K 平浪橋南側", "label": "台2線70.1K 平浪橋南側", "metadata": {} }],
  "dates": [{ "value": "2024-06-03", "label": "2024-06-03 崩塌發生", "metadata": {} }],
  "perspectives": [{ "value": "地質調查", "label": "地質調查", "metadata": {} }]
}
```

#### POST `/projects/upsert`

用途：建立或更新專案 metadata。前端建立專案時會呼叫此端點，將地點、日期、年份、視角寫入 PostgreSQL `projects.metadata`；這些欄位也是未來外部 JSON/API 節點來源的篩選條件。

Request：

```json
{
  "project_id": "proj_1770000000",
  "name": "台2線 70.1K",
  "region": "台2線70.1K 平浪橋南側",
  "date": "2024-06-03",
  "year": 2024,
  "perspective": "地質調查",
  "metadata": {}
}
```

Response：

```json
{ "status": "ok", "project_id": "proj_1770000000" }
```

#### GET `/project/files`

Query：

| 欄位 | 型別 | 預設 |
|---|---|---|
| `project_id` | string | `default` |

用途：列出專案內已上傳文件與 chunk 數。

#### DELETE `/project/clear`

Query：

| 欄位 | 型別 | 預設 |
|---|---|---|
| `project_id` | string | `default` |

用途：清空專案內 Qdrant、pages、markdown、source、OCR、images、relations。

Response：

```json
{ "status": "cleared" }
```

#### DELETE `/project/files/{filename}`

Query：

| 欄位 | 型別 | 預設 |
|---|---|---|
| `project_id` | string | `default` |

用途：移除單一文件與相關快取。

#### HEAD `/project/files/{filename}/pdf`

用途：檢查 PDF 原檔是否存在。

#### GET `/project/files/{filename}/pdf`

用途：讀取原始 PDF，回傳 `application/pdf` inline。

#### GET `/project/files/{filename}/ocr`

用途：取得或產生 OCR 文字位置。

Response：`OCRPageModel[]`

### 7.4 Page, Markdown, Images

#### GET `/project/pages/{filename}`

用途：取得 PDF 解析後 page text。

Response：`PageTextModel[]`

#### GET `/project/markdown/{filename}`

用途：取得清理後 Markdown 與 anchors。

Response：

```json
{
  "filename": "report.pdf",
  "markdown": "...",
  "anchors": []
}
```

#### GET `/project/pages/{filename}/images`

用途：取得頁面抽出的圖片。

Response：`PageImageModel[]`

### 7.5 VLM Selection

#### POST `/vlm/selection`

用途：原文 PDF 區域框選後，將裁切圖片送至 VLM 產生文字理解，使用者可確認後轉成 chunk。

Request：

```json
{
  "image_b64": "base64-png",
  "source_doc": "report.pdf",
  "source_page": 3,
  "project_id": "proj_xxx"
}
```

Response：

```json
{
  "label": "崩塌機制",
  "description": "...",
  "evidence_type": "image_selection",
  "source_doc": "report.pdf",
  "source_page": 3
}
```

### 7.6 Image Chunks

#### POST `/chunks/image`

用途：建立圖片 chunk，使用 CLIP image embedding。

Request：

```json
{
  "label": "現場崩塌照片",
  "source_doc": "report.pdf",
  "source_page": 3,
  "image_index": 0,
  "data_b64": "base64-png",
  "project_id": "proj_xxx"
}
```

#### GET `/chunks/image`

Query：

| 欄位 | 型別 | 預設 |
|---|---|---|
| `project_id` | string | `default` |

用途：列出 image chunks。

#### DELETE `/chunks/image/{chunk_id}`

用途：刪除 image chunk。

### 7.7 Manual Chunks

#### POST `/chunks/manual`

用途：建立使用者確認後的知識節點，會寫入向量資料庫。

Request：

```json
{
  "text": "平浪橋南側邊坡發生崩塌。",
  "label": "平浪橋南側崩塌",
  "source_doc": "report.pdf",
  "source_page": 3,
  "source_anchor": "^p3-key",
  "project_id": "proj_xxx",
  "region": null,
  "year": null,
  "perspective": null
}
```

#### GET `/chunks/manual`

Query：

| 欄位 | 型別 | 預設 |
|---|---|---|
| `project_id` | string | `default` |

用途：列出 manual / knowledge nodes。

#### DELETE `/chunks/manual/{chunk_id}`

Query：

| 欄位 | 型別 | 預設 |
|---|---|---|
| `project_id` | string | `default` |

用途：刪除節點，並移除相關 relation。

### 7.8 Relations

#### POST `/chunks/relations`

用途：建立 node relation，並建立 relation vector。

Request：

```json
{
  "from_chunk_id": "manual:a",
  "to_chunk_id": "manual:b",
  "label": "導致",
  "weight": 1.0,
  "project_id": "proj_xxx"
}
```

特性：

- 不允許 from / to 相同。
- 同一組 `from_chunk_id + to_chunk_id + label` 不可重複。
- `weight` 會限制在 0 到 1。

#### GET `/chunks/relations`

Query：

| 欄位 | 型別 | 預設 |
|---|---|---|
| `project_id` | string | `default` |

用途：列出 relations。

#### PATCH `/chunks/relations/{relation_id}/weight`

用途：更新 relation weight。

Body：

```json
{ "weight": 0.85 }
```

#### DELETE `/chunks/relations/{relation_id}`

Query：

| 欄位 | 型別 | 預設 |
|---|---|---|
| `project_id` | string | `default` |

用途：刪除 relation 與 relation vector。

### 7.9 Query

#### POST `/query`

用途：問答、檢索、LLM 回答、異常警示、query graph JSON 輸出。

Request：

```json
{
  "question": "平浪橋南側有災情？",
  "top_k": 5,
  "region": null,
  "year": null,
  "project_id": "proj_xxx"
}
```

Response：`QueryResponse`

```json
{
  "question": "...",
  "answer": "...",
  "retrieved_chunks": [],
  "graph_data": {
    "nodes": [],
    "edges": []
  },
  "anomalies": [],
  "router": {}
}
```

異常類型：

| type | 中文顯示 | 說明 |
|---|---|---|
| `out_of_domain` | 主題外問題 | 問題語意與目前知識庫主題不相符 |
| `insufficient_evidence` | 缺少明確佐證 | 問題與災害領域相關，但目前圖譜或文件沒有足夠證據 |
| `relation_contradiction` | 因果矛盾 | 使用者斷言的因果方向與已知 relation 相反 |

### 7.10 UMAP / Embedding Space

#### POST `/umap`

用途：輸出 embedding 空間座標，並寫出 `embedding_space_latest.json`。

Request：

```json
{
  "question": "平浪橋南側有災情？",
  "top_k": 5,
  "region": null,
  "year": null,
  "project_id": "proj_xxx"
}
```

Response：`UMAPResponse`

### 7.11 Graph JSON

#### GET `/graphs/json`

Query：

| 欄位 | 型別 | 預設 |
|---|---|---|
| `project_id` | string | `default` |

用途：列出目前 project 已輸出的 graph JSON。

Response：

```json
{
  "files": [
    {
      "filename": "graph_analysis_latest.json",
      "graph_name": "graph_analysis",
      "updated_at": 1779256466,
      "size_bytes": 81430,
      "node_count": 27,
      "edge_count": 351
    }
  ]
}
```

#### GET `/graphs/json/{filename}`

用途：讀取單一 graph JSON。

### 7.12 Graph Analysis

#### POST `/graph-analysis`

用途：建立 similarity graph、centrality、community、density，並寫出：

- `graph_analysis_latest.json`
- `knowledge_graph_latest.json`

Request：

```json
{
  "question": null,
  "top_k": 5,
  "threshold": 0.5,
  "region": null,
  "year": null,
  "project_id": "proj_xxx"
}
```

Response：`GraphAnalysisResponse`

```json
{
  "nodes": [],
  "edges": [],
  "num_communities": 1,
  "density": 1.0,
  "manual_relations": []
}
```

## 8. 前端畫面功能

| 區域 | 說明 |
|---|---|
| 左側工具列 | 專案、PDF 上傳、檔案列表 |
| 原文 | PDF 原檔檢視、框選圖片、VLM 辨識、建立 chunk |
| 詢問文件 | 一般文件問答 |
| 圖分析與編輯 | 節點、relation 建立/刪除/權重調整、異常警示 |
| 知識圖譜 | 知識節點與 relation 圖、節點對應 PDF 單頁 |
| Graph JSON | 類 Swagger API explorer，列出與檢視 graph JSON |

## 9. 已知限制

1. 問答 LLM 目前預設仍是 Ollama；若需要穩定工程語氣，未來可改接 API。
2. `/umap` 在部分本機環境可能因 embedding/model lock 較慢，適合展示但不建議當核心驗收依據。
3. 目前無使用者登入與權限控管，資料以本機 project_id 區隔。
4. Graph JSON 目前輸出 latest snapshot，尚未保留每次歷史版本。
5. `README.md` 仍有舊版 FAISS / Claude / D3 敘述，若要交付建議後續同步更新。

## 10. 後續可優化項目

目前暫時不需要再加大功能。若要持續優化，建議優先順序如下：

1. 將問答 LLM 從 Ollama 切到 API provider，提高回答穩定性。
2. Graph JSON 增加版本化輸出，例如 `graph_analysis_YYYYMMDD_HHMMSS.json`。
3. 增加一鍵「驗收報告」輸出，整理 node 數、relation 數、異常測試結果與 graph JSON 路徑。
4. 將 `/umap` 改成非同步 job，避免大型資料時阻塞。
5. 補 API synthetic tests，至少覆蓋 ingest、manual chunk、relation、query、graph-analysis、graphs/json。
6. 更新 `README.md`，避免與目前 Qdrant / VLM / GraphRAG 架構不一致。

## 11. 建議驗收測試

### 11.1 基本流程

1. 建立專案。
2. 上傳 GeoPORT PDF。
3. 確認左側檔案列表出現 PDF。
4. 進入圖分析與編輯。
5. 確認節點與 relation 出現。
6. 進入知識圖譜。
7. 點選 node，確認右側顯示對應 PDF 單頁。
8. 進入 Graph JSON，確認可讀取 `graph_analysis_latest.json` 與 `knowledge_graph_latest.json`。

### 11.2 問答測試

| 問題 | 預期 |
|---|---|
| 平浪橋南側有災情？ | 正常回答，不觸發異常 |
| 平浪橋西側有災情？ | 回答缺少證據，觸發 `insufficient_evidence` |
| 牛肉麵一碗多少錢？ | 觸發 `out_of_domain` |

### 11.3 Relation 測試

1. 建立 A -> B relation。
2. 重複建立相同 A -> B + label。
3. 預期後端回傳 409，前端顯示已存在。
4. 調整 relation weight。
5. 重新整理圖分析，確認線條深淺變化。
