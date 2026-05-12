# MoRA-RAG + Graph Anomaly MVP

一週可展示原型：把災後調查文字資料匯入後，系統會做 agentic chunking、MoR 混合檢索、RAG 證據鏈、知識圖譜建構，以及 GNN-ready 的異常判定 baseline。

## MVP 功能

- 文件匯入：貼上調查報告文字，建立 chunk 與 metadata。
- MoR Router：依查詢動態分配地震、洪水、土石流、海嘯、災損等檢索預算。
- RAG trace：輸出 pipeline、router score、retrieval budget、evidence evaluator。
- Graph-RAG：建立 chunk、hazard、location、metric 節點與關係。
- 異常偵測：先以規則與圖統計 baseline 標記語意矛盾、數值異常、低頻關係與地理不一致。
- 可視化：React dashboard 顯示 RAG pipeline、知識圖譜、證據與異常結果。

## 啟動

```bash
npm install
npm run install:all
npm run dev
```

若本機已有其他 Python 專案，建議先建立 virtual environment：

```bash
python3 -m venv .venv
source .venv/bin/activate
npm run install:all
```

前端：http://localhost:5173  
後端：http://localhost:8000/api/health

## LLM API

目前預設不依賴外部 LLM，確保 demo 可離線跑。下一步可在 backend 新增 provider：

- `LLM_PROVIDER=openai`
- `OPENAI_API_KEY=...`
- `LLM_MODEL=gpt-4.1-mini`

建議讓 LLM 負責：

1. entity / relation 抽取
2. evidence evaluator
3. final answer rewrite

RAG trace、graph schema、anomaly score 仍由後端保存，避免結果不可追溯。

## 一週交付策略

第一版先完成可展示端到端 MVP；Neo4j、Qdrant、PyGOD / PyTorch Geometric 都保留 adapter 邊界。等資料樣本穩定後，再把本機 JSON store 替換成正式 DB，並將 baseline anomaly 換成 graph autoencoder 或 PyGOD 模型。
