# PoC RAG Evaluation

This folder contains a small deterministic evaluation harness for the Visual RAG API.

Run the backend first, ingest the target PDF/project, then run:

```bash
python3 backend/evals/run_eval.py --base-url http://127.0.0.1:8000
```

Outputs:

- `backend/evals/eval_report.json`
- `backend/evals/eval_report.md`

Case files:

- `eval_cases.jsonl`: small smoke-test set.
- `geoport_vlm_cases.jsonl`: 40-case GeoPORT VLM benchmark covering location,
  numeric, time, causal-chain, visual interpretation, cross-page, out-of-domain,
  and contradiction questions.

Current metrics:

- `source_page_hit`: at least one expected page was retrieved.
- `source_page_recall`: fraction of expected pages retrieved.
- `answer_point_coverage`: expected answer phrases found in the answer.
- `relation_hit`: at least one expected graph relation label appeared.
- `anomaly_match`: expected anomaly type matched the API response.

The first pass intentionally avoids extra dependencies. Add Ragas/DeepEval after the
case set is stable and the team wants LLM-as-judge scores such as faithfulness,
answer relevancy, and correctness.
