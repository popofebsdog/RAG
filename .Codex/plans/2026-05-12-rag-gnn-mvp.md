# 任務：一週完成 MoRA-RAG + 可視化 + 異常偵測 MVP

## 成功條件
- [x] 可匯入災害調查文字資料，完成語意分塊與 metadata 擷取
- [x] 可查詢 RAG，輸出回答、來源證據、Router 分流與檢索流程
- [x] 可建立知識圖譜節點與邊，呈現事件、地點、災害、指標、來源關聯
- [x] 可對新輸入資料做異常判定，輸出異常分數與原因
- [x] 可視化 Dashboard 顯示 RAG pipeline、知識圖譜、證據表與異常結果
- [x] 可在本機啟動前後端並完成基本驗證

## 步驟
- [x] Step 1：建立專案骨架、七天開發計畫與 README
- [x] Step 2：實作 FastAPI 後端資料模型、ingestion、agentic chunking
- [x] Step 3：實作本機 RAG 檢索、MoR router、rerank、evidence evaluator
- [x] Step 4：實作知識圖譜建構與異常偵測 baseline
- [x] Step 5：實作 React 可視化 dashboard
- [x] Step 6：串接前後端 API，補 demo seed 資料
- [x] Step 7：執行測試、啟動服務、整理交付說明

## 注意事項
- 一週期限以可展示 MVP 為優先，GNN 先保留 PyGOD / PyTorch Geometric adapter 介面。
- 第一版不依賴外部 LLM API，避免 demo 因金鑰或網路失敗；後續可加 LLM provider adapter。
- Graph DB 與 Vector DB 先用本機 JSON 模擬，README 說明替換為 Neo4j / Qdrant 的位置。
