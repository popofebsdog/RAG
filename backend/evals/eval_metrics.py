from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


@dataclass
class EvalCase:
    id: str
    question: str
    project_id: str = "default"
    top_k: int = 5
    expected_answer_points: list[str] = field(default_factory=list)
    expected_source_pages: list[int] = field(default_factory=list)
    expected_relation_labels: list[str] = field(default_factory=list)
    expected_anomaly: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvalCase":
        return cls(
            id=str(data["id"]),
            question=str(data["question"]),
            project_id=str(data.get("project_id") or "default"),
            top_k=int(data.get("top_k") or 5),
            expected_answer_points=[str(v) for v in data.get("expected_answer_points", [])],
            expected_source_pages=[int(v) for v in data.get("expected_source_pages", [])],
            expected_relation_labels=[str(v) for v in data.get("expected_relation_labels", [])],
            expected_anomaly=data.get("expected_anomaly"),
        )


def score_case(case: EvalCase, response: dict[str, Any]) -> dict[str, float]:
    retrieved = response.get("retrieved_chunks") or []
    answer = str(response.get("answer") or "")
    anomalies = response.get("anomalies") or []
    edges = (response.get("graph_data") or {}).get("edges") or []

    retrieved_pages = {int(chunk.get("source_page") or 0) for chunk in retrieved}
    expected_pages = set(case.expected_source_pages)
    source_page_hit = _hit(expected_pages, retrieved_pages)
    source_page_recall = _recall(expected_pages, retrieved_pages)

    normalized_answer = _normalize_text(answer)
    found_points = {
        point
        for point in case.expected_answer_points
        if point and _normalize_text(point) in normalized_answer
    }
    answer_point_coverage = _ratio(len(found_points), len(case.expected_answer_points))

    relation_labels = {str(edge.get("label") or "") for edge in edges}
    relation_labels.update(
        str(chunk.get("label") or "")
        for chunk in retrieved
        if chunk.get("node_type") == "relation" or str(chunk.get("chunk_id") or "").startswith("relation:")
    )
    found_relations = {label for label in case.expected_relation_labels if label in relation_labels or label in answer}
    relation_hit = _hit(set(case.expected_relation_labels), found_relations)

    anomaly_types = {str(item.get("type") or "") for item in anomalies}
    if case.expected_anomaly:
        anomaly_match = 1.0 if case.expected_anomaly in anomaly_types else 0.0
    else:
        anomaly_match = 1.0 if not anomaly_types else 0.0

    return {
        "source_page_hit": source_page_hit,
        "source_page_recall": source_page_recall,
        "answer_point_coverage": answer_point_coverage,
        "relation_hit": relation_hit,
        "anomaly_match": anomaly_match,
    }


def summarize(scores: list[dict[str, float]]) -> dict[str, float]:
    if not scores:
        return {}
    keys = sorted({key for score in scores for key in score})
    return {key: round(sum(score.get(key, 0.0) for score in scores) / len(scores), 4) for key in keys}


def _hit(expected: set[Any], actual: set[Any]) -> float:
    if not expected:
        return 1.0
    return 1.0 if expected & actual else 0.0


def _recall(expected: set[Any], actual: set[Any]) -> float:
    if not expected:
        return 1.0
    return _ratio(len(expected & actual), len(expected))


def _ratio(value: int, total: int) -> float:
    if total <= 0:
        return 1.0
    return round(value / total, 4)


def _normalize_text(text: str) -> str:
    value = str(text).casefold()
    value = value.replace("毫米", "mm").replace("公釐", "mm")
    value = value.replace("公尺", "m").replace("米", "m")
    value = value.replace("平方公尺", "m2").replace("立方公尺", "m3")
    value = value.replace("°", "度")
    value = re.sub(r"(\d+)\s*月\s*(\d+)\s*日", r"\1/\2", value)
    value = re.sub(r"(\d+)\s*[點時]\s*(\d{2})?", lambda m: f"{m.group(1)}:{m.group(2) or '00'}", value)
    value = re.sub(r"\s+", "", value)
    return value
