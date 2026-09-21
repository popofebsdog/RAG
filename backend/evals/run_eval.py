from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from eval_metrics import EvalCase, score_case, summarize


ROOT = Path(__file__).resolve().parent
DEFAULT_CASES = ROOT / "eval_cases.jsonl"
DEFAULT_REPORT_JSON = ROOT / "eval_report.json"
DEFAULT_REPORT_MD = ROOT / "eval_report.md"


def main() -> int:
    args = _parse_args()
    cases = load_cases(args.cases)
    results: list[dict[str, Any]] = []

    for case in cases:
        started = time.time()
        try:
            response = query_api(args.base_url, case)
            scores = score_case(case, response)
            error = ""
        except Exception as exc:
            response = {}
            scores = {}
            error = str(exc)
        results.append({
            "id": case.id,
            "question": case.question,
            "project_id": case.project_id,
            "latency_sec": round(time.time() - started, 3),
            "scores": scores,
            "error": error,
            "answer": response.get("answer", ""),
            "retrieved_chunks": response.get("retrieved_chunks", []),
            "anomalies": response.get("anomalies", []),
        })

    report = {
        "base_url": args.base_url,
        "case_count": len(cases),
        "summary": summarize([item["scores"] for item in results if item["scores"]]),
        "results": results,
    }
    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_md.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report_md.write_text(render_markdown(report), encoding="utf-8")
    print(f"Wrote {args.report_json}")
    print(f"Wrote {args.report_md}")
    return 1 if any(item["error"] for item in results) else 0


def load_cases(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cases.append(EvalCase.from_dict(json.loads(line)))
    return cases


def query_api(base_url: str, case: EvalCase) -> dict[str, Any]:
    payload = json.dumps({
        "question": case.question,
        "top_k": case.top_k,
        "project_id": case.project_id,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/query",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# RAG Eval Report",
        "",
        f"- Base URL: `{report['base_url']}`",
        f"- Cases: {report['case_count']}",
        "",
        "## Summary",
        "",
    ]
    for key, value in report["summary"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Cases", ""])
    for item in report["results"]:
        status = "ERROR" if item["error"] else "OK"
        lines.append(f"### {item['id']} - {status}")
        lines.append("")
        lines.append(f"Question: {item['question']}")
        lines.append("")
        if item["error"]:
            lines.append(f"Error: `{item['error']}`")
        else:
            score_text = ", ".join(f"{k}={v}" for k, v in item["scores"].items())
            pages = sorted({chunk.get("source_page") for chunk in item["retrieved_chunks"] if chunk.get("source_page")})
            anomalies = [flag.get("type") for flag in item["anomalies"]]
            lines.append(f"Scores: {score_text}")
            lines.append(f"Retrieved pages: {pages}")
            lines.append(f"Anomalies: {anomalies}")
        lines.append("")
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PoC RAG eval cases against the local API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
