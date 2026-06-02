# Visual RAG System

Visual RAG System 是一個可維護的 GraphRAG 原型系統，專門處理災害與工程類 PDF 報告。

系統會把技術型 PDF 內容轉換為可編輯的知識節點、節點關係、向量索引，以及互動式知識圖譜。它特別適合關鍵證據可能分散在文字、表格、圖像、地圖與標註影像中的報告。

## 目前版本可做的事

- **VLM PDF 理解**：將 PDF 頁面轉成影像後交由視覺語言模型解析，讓以圖像為主的報告也能轉成結構化知識。
- **人機協作的知識節點審查**：上傳 PDF 後會先產出候選知識節點，使用者可先核准或編輯，再建立知識圖譜。
- **知識圖譜編修**：可檢視知識節點、建立或調整節點關係，並將關係向量回寫到向量資料庫。
- **具查詢意識的圖譜視覺化**：問題會以暫時性的查詢節點顯示在圖上；若屬於領域內問題，會連到命中的知識節點；若屬於領域外問題，會顯示紅色警示節點。
- **異常警示層**：將領域外問題與證據不足的問題以視覺方式標示出來，同時避免污染正式知識圖譜。
- **回溯原始 PDF 依據**：知識節點會保留來源文件與頁碼中繼資料，方便使用者回看原始 PDF 脈絡。
- **專案隔離**：每個專案都會分開保存 PDF、知識節點、節點關係、圖譜 JSON 與查詢紀錄。
- **Graph JSON 瀏覽器**：可直接從 UI 瀏覽系統輸出的圖譜 JSON 檔。
- **偏向正式部署的儲存方式**：PostgreSQL 儲存結構化中繼資料；Qdrant 儲存向量嵌入。

## 目前工作流程

```mermaid
flowchart LR
  A["建立 / 選擇專案"] --> B["上傳 PDF"]
  B --> C["VLM 解析 PDF 頁面"]
  C --> D["候選知識節點"]
  D --> E["使用者審查 / 編修節點"]
  E --> F["提交到 PostgreSQL + Qdrant"]
  F --> G["建立知識圖譜"]
  G --> H["編輯節點關係"]
  G --> I["提出問題"]
  I --> J["查詢節點 + 高亮證據"]
  I --> K["必要時顯示領域外警示"]
```

## 技術堆疊

| 層級 | 技術 |
|---|---|
| 後端 | Python + FastAPI |
| 前端 | Vue 3 + TypeScript + Vite |
| PDF 轉譯 | PyMuPDF |
| VLM 解析 | Anthropic Claude Vision 或 OpenAI Vision 相容模型 |
| LLM 回答生成 | 預設為 OpenAI，並可退回 Anthropic / Ollama |
| 向量資料庫 | Qdrant |
| 中繼資料資料庫 | PostgreSQL 16 |
| 圖譜分析 | NetworkX |
| 圖譜 UI | Cytoscape.js |
| 嵌入投影 | UMAP |
| 嵌入模型 | 預設為 Ollama 的 nomic-embed-text |

## 快速開始

### 1. 啟動儲存服務

```bash
docker compose up -d postgres qdrant
```

本機預設埠號：

- PostgreSQL: localhost:55432
- Qdrant: localhost:6333

### 2. 設定後端環境

```bash
cd backend
cp .env.example .env
```

啟動 Ollama 並拉取 embedding 模型：

```bash
ollama pull nomic-embed-text
```

至少要設定一組 VLM / API 金鑰：

```bash
ANTHROPIC_API_KEY=<your-anthropic-key>
# 或
OPENAI_API_KEY=<your-openai-key>
```

backend/.env.example 內常用的預設值如下：

```bash
DATABASE_URL=postgresql://visual_rag:visual_rag_password@localhost:55432/visual_rag
QDRANT_URL=http://localhost:6333
OLLAMA_URL=http://localhost:11434
EMBED_MODEL=nomic-embed-text
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4.1-mini
VLM_PROVIDER=anthropic
ANTHROPIC_VISION_MODEL=claude-sonnet-4-5
OPENAI_VISION_MODEL=gpt-4.1-mini
```

交接給維運人員時，請保留 DATABASE_URL 與 QDRANT_URL。除非你刻意要用本機檔案模式向量儲存，否則不要在正式環境設定 QDRANT_PATH。

## 交付廠商時的環境檢查清單

若要把系統交給外部維運或廠商，請要求他們以 backend/.env.example 為基礎建立 backend/.env，並填入以下設定。

### 必填

| Key | 需填內容 | 範例 / 說明 |
|---|---|---|
| DATABASE_URL | PostgreSQL 連線字串 | postgresql://visual_rag:visual_rag_password@localhost:55432/visual_rag |
| QDRANT_URL | Qdrant 服務 URL | http://localhost:6333 |
| OLLAMA_URL | embedding 用的 Ollama 服務 URL | http://localhost:11434 |
| EMBED_MODEL | Ollama embedding 模型 | nomic-embed-text |
| LLM_PROVIDER | 回答生成使用的模型供應商 | 建議使用 openai |
| OPENAI_API_KEY | OpenAI API key；當 LLM_PROVIDER=openai 或 VLM_PROVIDER=openai 時必填 | 請妥善保管，不要提交進版控 |
| OPENAI_MODEL | 文字回答模型 | gpt-4.1-mini |
| VLM_PROVIDER | PDF 視覺解析供應商 | 如果只用 OpenAI 計費，建議設為 openai |
| OPENAI_VISION_MODEL | PDF 頁面理解用的 vision 模型 | gpt-4.1-mini |
| DSM_API_BASE_URL | 外部影像辨識節點所需的 DSM API 主機與埠號 | http://localhost:3000 |
| DSM_API_TIMEOUT | DSM API 逾時秒數 | 8 |

### 必要的本機服務安裝

```bash
docker compose up -d postgres qdrant
ollama pull nomic-embed-text
```

廠商應至少驗證：

```bash
curl http://127.0.0.1:8000/health
curl http://localhost:6333/collections
curl http://localhost:11434/api/tags
```

### 可選設定 / 調校參數

| Key | 用途 | 建議預設值 |
|---|---|---|
| VLM_MAX_PAGES | VLM 可解析的最大 PDF 頁數 | 20 |
| VLM_RENDER_DPI | 送給 VLM 前的 PDF 渲染解析度 | 160 |
| VLM_CONCURRENCY | 同時平行處理頁數 | 4 |
| VLM_TIMEOUT | VLM 請求逾時秒數 | 120 到 180 |
| VLM_CACHE | 是否重用 VLM 頁面快取 | 1 |
| CHUNK_MODE | 知識節點前處理模式 | semantic |
| TOP_K | 檢索證據數量 | 5 |
| SEMANTIC_THRESHOLD | 語意切分門檻 | 正式環境建議 0.70；測試時才考慮降低 |
| MANUAL_BOOST | 已審查知識節點於檢索時的權重加成 | 0.15 |
| DSM_API_BASE_URL | 廠商 DSM 影像辨識 API 基底 URL | http://localhost:3000 |
| DSM_API_TIMEOUT | DSM API 讀取逾時秒數 | 8 |

## 廠商 DSM API 整合

左側專案表單中的 **Location** 與 **Date** 下拉選單，也同時是接到廠商 DSM 影像辨識系統的橋接資訊。

當使用者建立專案時：

1. 前端會把選定的 location / date 傳給本系統。
2. 後端會從 backend/config/project_filter_options.json 讀取相符的 DSM 中繼資料。
3. 若中繼資料內有 DSM 結果 JSON 路徑，後端就會呼叫 DSM_API_BASE_URL 指向的 API。
4. DSM 結果 JSON 會被轉換成 external_vision 類型的知識節點。
5. 這些節點會寫入 PostgreSQL 與 Qdrant，並在知識圖譜中以獨立 DSM 顏色顯示。

### 廠商需提供或確認的內容

| 項目 | 必要值 |
|---|---|
| DSM API base URL | 例如：http://localhost:3000 |
| 結果 JSON endpoint path | 例如：/api/dsm-images/results/19_result.json |
| 結果影像 endpoint path，可選 | 例如：/api/dsm-images/results/19_result.jpg |
| 偵測結果 JSON schema | 建議包含 detections、objects、instances、results、items 或 features 等鍵名 |
| 類別標籤 | 例如：fall、normal |
| 信心分數欄位，可選 | 例如：confidence、score 或 probability |
| 邊界框 / 幾何欄位，可選 | 例如：bbox、box、bounds、centroid 或 area |

### 後端環境變數

請把以下設定加入 backend/.env：

```bash
DSM_API_BASE_URL=http://localhost:3000
EXTERNAL_VISION_API_URL=http://localhost:3000
DSM_API_TIMEOUT=8
```

DSM_API_BASE_URL 是主要設定。EXTERNAL_VISION_API_URL 只是為了將來擴充非 DSM 的外部影像辨識服務而保留的別名。前端不會把這些值硬編碼；若廠商更改 DSM 主機或埠號，只需更新後端 env。

### 下拉選單中繼資料對應

每個 location / date 選項都可以在 backend/config/project_filter_options.json 中附帶 DSM 中繼資料。

範例：

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

後端目前接受以下任一 JSON 路徑鍵名：

- dsm_result_json_path
- outputJsonPath
- output_json_path
- resultJsonPath

也支援只提供檔名的寫法：

```json
{
  "outputJsonFilename": "19_result.json"
}
```

系統會自動解析成：

```text
/api/dsm-images/results/19_result.json
```

### 本系統會使用到的 DSM API 端點

本系統在建立專案時，只需要讀取最終完成的 DSM JSON 結果：

| Method | Endpoint | 用途 |
|---|---|---|
| GET | /api/dsm-images/results/:filename | 讀取最終的 DSM 結果 JSON |

廠商仍可獨立運作完整的 DSM 工作流程：

| Method | Endpoint | 用途 |
|---|---|---|
| GET | /api/dsm | 列出 DSM 檔案 |
| GET | /api/dsm/:id | 取得單一 DSM 檔案 |
| POST | /api/dsm/upload | 上傳 DSM 檔案 |
| POST | /api/dsm/start-detect/:id | 啟動辨識 |
| GET | /api/dsm/jobs/:jobId | 查詢工作狀態 |
| GET | /api/dsm/jobs/pending | 列出待處理工作 |

### 本系統的預覽端點

前端在正式建立專案前，會先呼叫這個 API 來顯示 DSM 資料是否存在：

```bash
GET /external/dsm/preview?location=台2線70.1K%20平浪橋南側&date=2024-06-03
```

回應格式：

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

### Anthropic 替代方案

若廠商要用 Anthropic 來處理回答生成或 VLM 解析，可填入：

```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=<vendor-anthropic-key>
ANTHROPIC_MODEL=claude-sonnet-4-5
VLM_PROVIDER=anthropic
ANTHROPIC_VISION_MODEL=claude-sonnet-4-5
```

請確認 Anthropic 帳戶有足夠額度；若額度不足，當 LLM_PROVIDER=anthropic 時，/query 會失敗。

### 正式環境不要使用

```bash
QDRANT_PATH=./qdrant_data
```

QDRANT_PATH 僅適用於本機檔案模式測試。交付廠商時請保持註解狀態，改用 QDRANT_URL 讓向量存入 Qdrant 服務。

### 3. 啟動後端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

API：http://127.0.0.1:8000

### 4. 啟動前端

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

應用程式：http://127.0.0.1:5173

### 本機一鍵啟動

```bash
./start.sh
```

此腳本會啟動 PostgreSQL、Qdrant、後端與前端。若 backend/.env 不存在，腳本會自動建立，並提示你設定 API key。

## 使用方式

1. 從左側工作區建立或選擇專案。
2. 上傳 PDF。
3. 等待 VLM 完成解析。
4. 審查候選知識節點。
5. 確認並建立知識圖譜。
6. 使用 **Knowledge Graph Edit** 檢視節點並調整節點關係。
7. 在右側面板提問。
8. 在圖譜上檢查暫時性查詢節點與高亮證據。

重要行為：

- 關閉審查對話框只會隱藏視窗，不會清掉待審內容；待審資料仍會保留在左側上傳面板。
- 按下 **Discard** 會移除待審的 VLM 結果。
- 查詢節點只是暫時性的 UI 狀態，不會寫入 PostgreSQL、Qdrant 或圖譜 JSON。
- 領域外問題不會把知識節點高亮為證據。

## 核心概念

| 名詞 | 說明 |
|---|---|
| Knowledge node | 從 PDF 文字或視覺內容萃取出來、且已審查的知識單位。 |
| Node relation | 兩個知識節點之間的有向關係，例如 causes、located_at、observed_at、supports。 |
| Knowledge graph | 由知識節點與節點關係所形成的專案級圖譜。 |
| Query node | 代表最新問題的暫時性視覺節點。 |
| Warning node | 用於顯示領域外或證據不足問題的暫時性紅色節點。 |

## API 概觀

### 專案與檔案

| Method | Path | 用途 |
|---|---|---|
| GET | /health | 服務狀態 |
| GET | /project/filter-options | 專案中繼資料下拉來源 |
| POST | /projects/upsert | 儲存專案中繼資料 |
| GET | /project/files | 列出專案 PDF |
| DELETE | /project/clear | 清除整個專案資料 |
| DELETE | /project/files/{filename} | 刪除單一 PDF 與其衍生資料 |
| GET | /project/files/{filename}/pdf | 提供原始 PDF |
| GET | /project/files/{filename}/info | PDF 中繼資料 |
| GET | /project/files/{filename}/page-image/{page_num}.png | 提供渲染後的 PDF 頁面影像 |

### VLM 匯入與審查

| Method | Path | 用途 |
|---|---|---|
| POST | /ingest/preview | 上傳 PDF 並產生候選知識節點 |
| POST | /ingest/commit | 提交審查後的節點與關係 |
| POST | /ingest | 舊版的直接匯入端點 |
| POST | /vlm/selection | 解讀使用者框選的 PDF 影像區域 |

### 知識節點與節點關係

| Method | Path | 用途 |
|---|---|---|
| GET | /chunks/manual | 列出審查後 / 使用者建立的知識節點 |
| POST | /chunks/manual | 建立知識節點 |
| DELETE | /chunks/manual/{chunk_id} | 刪除知識節點 |
| GET | /chunks/relations | 列出節點關係 |
| POST | /chunks/relations | 建立節點關係 |
| PATCH | /chunks/relations/{relation_id}/weight | 更新關係權重 |
| DELETE | /chunks/relations/{relation_id} | 刪除節點關係 |

API 內部仍在某些端點名稱沿用 chunk，這只是為了相容舊介面；UI 對外顯示仍使用 **knowledge node**。

### 查詢與視覺化

| Method | Path | 用途 |
|---|---|---|
| POST | /query | 提問並取得回答、檢索證據與警示 |
| POST | /graph-analysis | 建立圖譜分析視圖 |
| POST | /umap | 建立 embedding 投影 |
| GET | /graphs/json | 列出已輸出的圖譜 JSON 檔 |
| GET | /graphs/json/{filename} | 讀取單一圖譜 JSON 檔 |

## 儲存模型

### PostgreSQL

儲存可維護的結構化中繼資料：

- projects
- PDF 文件中繼資料
- 知識節點紀錄
- 節點關係紀錄
- 圖譜輸出中繼資料
- 查詢紀錄與異常紀錄

### Qdrant

儲存向量化後的檢索物件：

- 已審查的知識節點
- 節點關係
- 由影像或框選區域衍生的知識

### 檔案儲存

本機資料夾負責儲存二進位與產生出的資產：

- 原始 PDF
- 渲染後頁面影像
- OCR / VLM 快取
- 圖譜 JSON 輸出

若要正式部署，請把這些資料夾掛到持久化儲存，或改接物件儲存服務。

## Repository 結構

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

## 驗證指令

```bash
cd backend
python3 -m py_compile main.py rag/*.py

cd ../frontend
npm run build
```

## 目前範圍

這個專案是偏實務、可維護的原型，不是完整託管式 SaaS 平台。它已經做到專案資料隔離，並支援 PostgreSQL + Qdrant；但若要正式部署，仍建議補上：

- 身分驗證與授權
- PDF 與頁面影像的受管物件儲存
- 備份與 migration 策略
- VLM 慢速解析工作的排程 / 佇列化
- 結構化可觀測性與錯誤回報