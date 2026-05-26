# Visual RAG System — 功能與介面說明

## 系統概述

Visual RAG System 是一套以**知識圖譜為核心**的文件問答平台。使用者上傳 PDF 後，系統可自動或手動切分內容（文字＋圖片），將切片儲存為向量，再透過語意搜尋與圖分析找到最相關的段落，最終由 LLM 生成答案。

### 技術棧

| 層級 | 技術 |
|------|------|
| 後端 | Python · FastAPI · Qdrant（向量資料庫）· Ollama（本地 LLM） |
| 文字 Embedding | `nomic-embed-text`（768 維，via Ollama） |
| 圖片 Embedding | CLIP `ViT-B/32`（512 維） |
| PDF 解析 | PyMuPDF4LLM（文字 / Markdown）· PyMuPDF（圖片抽取） |
| 前端 | Vue 3 · TypeScript · Tailwind CSS · Cytoscape.js |

---

## 介面結構

```
┌──────────────── Top Bar ────────────────────────────────┐
│  專案名稱  [地區·年份]   PyMuPDF4LLM Qdrant Claude …   [文件閱讀器] [詢問] [EN/中]  │
├─────────┬───────────────────────────────┬───────────────┤
│  左側欄  │        中央畫布（可視化）         │   右側聊天欄   │
│  Rail   │   圖分析與編輯 / 知識圖譜 /      │  ChatPanel   │
│         │   Embedding                     │               │
└─────────┴───────────────────────────────┴───────────────┘
                      ↕（浮層）
              DocumentReader（文件閱讀器）
```

---

## 各模組說明

### 1. 左側欄（Rail）

**專案管理 — ProjectPanel**

- 建立、切換、刪除專案，每個專案獨立儲存文件、切片與關係
- 支援設定專案的地區（Region）與年份（Year）metadata，可在搜尋時作為過濾條件

**上傳面板 — UploadPanel**

- 拖放或點擊上傳 PDF
- **PDF 解析器**：固定使用 PyMuPDF4LLM，輸出 RAG 導向 Markdown，並保留閱讀順序與表格。
- **切分策略**：
  - `auto`：系統自動依段落切分，直接嵌入向量資料庫
  - `manual`：上傳後開啟文件閱讀器，由使用者手動圈選段落命名

**檔案列表**

- 顯示目前專案已上傳的 PDF 及各自的 chunk 數量
- 可單筆刪除或一鍵清除整個專案資料

**檢索結果**

- 提問後顯示被召回的 chunk ID 與相似度分數

---

### 2. 中央畫布（VisualizationPanel）

頂部有 Tab 列，切換三種視圖：

#### 2-1. 圖分析與編輯（Graph Analysis & Edit）

- 顯示自動 chunk、手動 node 與手動關係邊。
- 點選節點後可設定為起點或終點，輸入關係標籤與 weight 後寫入後端。
- 關係會同時寫入 `relations_cache/`，並以 `relation:*` 向量節點存入 Qdrant。
- 左側 Metrics 只統計目前畫布可見節點與邊，不把隱藏的 relation vector 算進去。
- 提案驗收區塊顯示：手動 node 入庫、關係向量化、災害分類標籤、RAN 權重關係、異常偵測接口。

#### 2-2. 知識圖譜（Knowledge Graph）

- 以 Cytoscape.js 呈現自動切分的 chunk 節點與語意關係邊
- 節點顏色代表所屬社群（community detection）
- 點擊節點可查看來源文件、節點類型、災害標籤與摘要文字
- 底部可調整**相似度閾值**，即時過濾低權重的邊
- 預設隱藏 `relation` 向量節點，只保留真正的手動關係箭頭

#### 2-3. Embedding 空間（Embedding Space）

- 以 UMAP 將所有 chunk 的 768 維向量降至 2D 呈現
- 手動 chunk（橘）、自動 chunk（藍）、查詢點（紅星）以顏色區分
- 顯示語意鄰近關係，可觀察哪些段落在向量空間中彼此接近
- `relation` 向量預設隱藏，可用「顯示關係向量」開關檢查關係是否已進入向量資料庫

---

### 3. 文件閱讀器（DocumentReader）

點擊頂部「文件閱讀器」按鈕開啟，以浮層形式呈現。

**側欄功能**

- 列出目前專案的所有 PDF，點擊切換文件
- 顯示已命名的文字 chunk 清單（可捲動定位、可刪除）
- 顯示已命名的文字 chunk 清單（可捲動定位、可刪除）

**文字標籤（Manual Text Chunk）**

1. 在文件內容中拖曳選取文字段落
2. 浮現輸入框，輸入名稱後按 Enter 建立 chunk
3. Chunk 會嵌入向量（Ollama nomic-embed-text）並存入 Qdrant

---

### 4. 聊天面板（ChatPanel）

- 輸入自然語言問題
- 後端流程：問題嵌入 → Qdrant 向量搜尋 → 圖關係增強召回 → LLM 生成答案
- 回傳：答案文字、引用的 chunk 清單、MoR Router 分數、異常偵測標記（Anomaly Flags）
- 提問後自動更新 UMAP 與圖分析，以查詢點為中心重新呈現結果

---

## 資料流程圖

```
PDF 上傳
  │
  ├── auto 模式 ──► PyMuPDF4LLM 解析 ──► 自動切分 ──► nomic-embed-text ──► Qdrant（visual_rag）
  │
  └── manual 模式 ──► 文件閱讀器
                         │
                         ├── 選取文字 ──► nomic-embed-text ──► Qdrant（visual_rag）
                         └── 圈選圖片 ──► CLIP ──────────────► Qdrant（visual_rag_images）

                               ↓
                        圖分析與編輯建立關係
                         │
                         └── 起點/終點 + label + weight ──► POST /chunks/relations ──► relations_cache/ + Qdrant relation node

                               ↓
                         使用者提問
                         │
                         └── 向量搜尋 + 圖關係 ──► LLM ──► 答案 + 來源引用
```

---

## 後端 API 摘要

| 端點 | 說明 |
|------|------|
| `POST /ingest` | 上傳並解析 PDF，支援 auto/manual 兩種策略 |
| `GET /project/files` | 列出專案檔案與 chunk 數量 |
| `GET /project/pages/{filename}` | 取得 PDF 各頁文字內容 |
| `GET /project/pages/{filename}/images` | 取得 PDF 各頁圖片（Base64） |
| `POST /chunks/manual` | 建立手動文字 chunk（含向量嵌入） |
| `POST /chunks/image` | 建立圖片 chunk（CLIP 嵌入） |
| `POST /chunks/relations` | 建立節點關係（含 weight） |
| `PATCH /chunks/relations/{id}/weight` | 更新關係權重 |
| `POST /query` | 語意問答（搜尋 + LLM 生成） |
| `POST /umap` | 計算並回傳 2D UMAP 投影結果 |
| `POST /graph-analysis` | 圖結構分析（PageRank、社群、密度） |

---

## 向量資料庫結構

| Collection | 維度 | 內容 |
|------------|------|------|
| `visual_rag` | 768 | 自動 chunk + 手動文字 chunk + relation vector（nomic-embed-text） |
| `visual_rag_images` | 512 | 圖片 chunk（CLIP ViT-B/32） |

每筆 point 的 payload 均包含 `project_id`，所有查詢皆依此欄位隔離專案資料。

---

## 節點類型說明（圖分析與編輯圖例）

| 顏色 | 形狀 | 類型 |
|------|------|------|
| 橘色 ● | 圓形 | 手動文字 chunk |
| 藍色 ■ | 圓角方形 | 圖片 chunk |
| 灰色 ● | 圓形 | 自動 chunk（AI 切分） |
| 橘色線 | 箭頭 | 已儲存的手動關係邊 |
| 灰色線 | 實線 | 自動相似度邊 |
| 藍色 ◆ | 菱形 | relation vector，預設在圖分析與知識圖譜隱藏，Embedding 可切換顯示 |
