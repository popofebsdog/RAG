from __future__ import annotations

import math
import re
import uuid
from collections import Counter, defaultdict

from .models import Anomaly, Chunk, DocumentRecord, Evidence, GraphEdge, GraphNode

HAZARD_KEYWORDS = {
    "earthquake": ["地震", "震度", "斷層", "餘震", "液化", "土壤液化"],
    "flood": ["洪水", "淹水", "積水", "暴雨", "豪雨", "雨量", "排水"],
    "landslide": ["土石流", "崩塌", "邊坡", "滑動", "落石", "坡地"],
    "tsunami": ["海嘯", "潮位", "沿岸", "海岸", "港口", "浪高"],
    "damage": ["災損", "橋梁", "道路", "中斷", "倒塌", "受損"],
}

LOCATION_PATTERN = re.compile(r"(?:於|在|位於|鄰近|靠近)([^，。；、\s]{2,18})")
DATE_PATTERN = re.compile(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?")
METRIC_PATTERN = re.compile(r"\d+(?:\.\d+)?\s?(?:mm|毫米|公尺|m|級|度|cm|公分)")


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    words = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", lowered)
    bigrams = [lowered[i : i + 2] for i in range(max(len(lowered) - 1, 0)) if "\n" not in lowered[i : i + 2]]
    return words + bigrams


def detect_hazards(text: str) -> list[str]:
    hits = []
    for hazard, keywords in HAZARD_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            hits.append(hazard)
    return hits or ["general"]


def clean_location(raw: str) -> str:
    location = raw
    for marker in ["發生", "累積", "觀察", "監測", "通報", "附近", "沿線"]:
        if marker in location:
            head = location.split(marker, 1)[0]
            location = head + marker if marker in ["附近", "沿線"] else head
    return location.strip("，。；、 ")


def extract_metadata(text: str) -> tuple[list[str], list[str], list[str]]:
    locations = sorted({loc for loc in (clean_location(match.group(1)) for match in LOCATION_PATTERN.finditer(text)) if len(loc) >= 2})[:8]
    dates = sorted(set(DATE_PATTERN.findall(text)))[:8]
    metrics = sorted(set(METRIC_PATTERN.findall(text)))[:10]
    return locations, dates, metrics


def summarize(text: str, limit: int = 110) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:limit] + ("..." if len(compact) > limit else "")


def agentic_chunk(title: str, text: str, source: str) -> tuple[DocumentRecord, list[Chunk]]:
    document_id = f"doc-{uuid.uuid4().hex[:10]}"
    blocks = [block.strip() for block in re.split(r"\n{2,}|(?<=[。！？!?])\s+", text) if block.strip()]
    chunks: list[str] = []
    current = ""
    for block in blocks:
        if len(current) + len(block) > 850 and current:
            chunks.append(current)
            current = block
        else:
            current = f"{current}\n{block}".strip()
    if current:
        chunks.append(current)

    records = []
    for index, chunk_text in enumerate(chunks, start=1):
        locations, dates, metrics = extract_metadata(chunk_text)
        records.append(
            Chunk(
                id=f"{document_id}-chunk-{index}",
                document_id=document_id,
                title=title,
                text=chunk_text,
                source=source,
                hazards=detect_hazards(chunk_text),
                locations=locations,
                dates=dates,
                metrics=metrics,
                summary=summarize(chunk_text),
            )
        )
    return DocumentRecord(id=document_id, title=title, source=source, chunk_ids=[c.id for c in records]), records


def router_scores(query: str) -> dict[str, float]:
    raw = {}
    for hazard, keywords in HAZARD_KEYWORDS.items():
        raw[hazard] = 0.05 + sum(1.0 for keyword in keywords if keyword in query)
    total = sum(raw.values()) or 1
    return {hazard: round(score / total, 3) for hazard, score in raw.items()}


def allocate_budget(scores: dict[str, float], top_k: int) -> dict[str, int]:
    selected = {hazard: score for hazard, score in scores.items() if score >= 0.12}
    if not selected:
        selected = dict(sorted(scores.items(), key=lambda item: item[1], reverse=True)[:2])
    budget = {hazard: max(1, round(score * top_k)) for hazard, score in selected.items()}
    while sum(budget.values()) > top_k:
        key = min(budget, key=budget.get)
        if budget[key] > 1:
            budget[key] -= 1
        else:
            break
    while sum(budget.values()) < top_k:
        key = max(selected, key=selected.get)
        budget[key] += 1
    return budget


def lexical_score(query: str, text: str) -> float:
    query_terms = Counter(tokenize(query))
    text_terms = Counter(tokenize(text))
    if not query_terms or not text_terms:
        return 0
    overlap = sum(min(count, text_terms[term]) for term, count in query_terms.items())
    norm = math.sqrt(sum(query_terms.values())) * math.sqrt(sum(text_terms.values()))
    return overlap / norm if norm else 0


def retrieve(query: str, chunks: list[Chunk], top_k: int) -> tuple[dict[str, float], dict[str, int], list[Evidence]]:
    scores = router_scores(query)
    budget = allocate_budget(scores, top_k)
    candidates: list[tuple[float, Chunk, str]] = []
    for hazard, limit in budget.items():
        scoped = [chunk for chunk in chunks if hazard in chunk.hazards or "general" in chunk.hazards]
        ranked = sorted(
            ((lexical_score(query, chunk.text) + scores.get(hazard, 0) * 0.18, chunk, hazard) for chunk in scoped),
            key=lambda item: item[0],
            reverse=True,
        )
        candidates.extend(ranked[:limit])

    dedup: dict[str, tuple[float, Chunk, str]] = {}
    for score, chunk, hazard in candidates:
        if chunk.id not in dedup or score > dedup[chunk.id][0]:
            dedup[chunk.id] = (score, chunk, hazard)

    evidences = []
    for score, chunk, _hazard in sorted(dedup.values(), key=lambda item: item[0], reverse=True)[:top_k]:
        evaluator = "pass" if score >= 0.05 else "weak-match"
        if any(word in chunk.text for word in ["矛盾", "不一致", "疑似"]):
            evaluator = "needs-review"
        evidences.append(
            Evidence(
                chunk_id=chunk.id,
                title=chunk.title,
                source=chunk.source,
                text=chunk.summary,
                score=round(score, 3),
                hazards=chunk.hazards,
                locations=chunk.locations,
                evaluator=evaluator,
            )
        )
    return scores, budget, evidences


def build_graph(chunks: list[Chunk]) -> dict[str, list[dict]]:
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    def add_node(node_id: str, label: str, node_type: str, score: float = 0) -> None:
        nodes[node_id] = GraphNode(id=node_id, label=label, type=node_type, score=max(score, nodes.get(node_id, GraphNode(id=node_id, label=label, type=node_type)).score))

    for chunk in chunks:
        add_node(chunk.id, chunk.title, "chunk", 0.4)
        for hazard in chunk.hazards:
            hid = f"hazard:{hazard}"
            add_node(hid, hazard, "hazard", 0.5)
            edges.append(GraphEdge(source=chunk.id, target=hid, label="classified_as", weight=0.8))
        for location in chunk.locations:
            lid = f"location:{location}"
            add_node(lid, location, "location", 0.45)
            edges.append(GraphEdge(source=chunk.id, target=lid, label="mentions", weight=0.7))
        for metric in chunk.metrics:
            mid = f"metric:{metric}"
            add_node(mid, metric, "metric", 0.35)
            edges.append(GraphEdge(source=chunk.id, target=mid, label="observes", weight=0.65))
    return {"nodes": [node.model_dump() for node in nodes.values()], "edges": [edge.model_dump() for edge in edges]}


def detect_anomalies(chunks: list[Chunk]) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    pair_counts: defaultdict[tuple[str, str], int] = defaultdict(int)
    for chunk in chunks:
        for hazard in chunk.hazards:
            for location in chunk.locations:
                pair_counts[(hazard, location)] += 1

    for chunk in chunks:
        text = chunk.text
        if "tsunami" in chunk.hazards and not any(word in text for word in ["海", "港", "沿岸", "潮", "岸"]):
            anomalies.append(
                Anomaly(
                    id=f"anom-{chunk.id}-tsunami-location",
                    severity="high",
                    score=0.88,
                    reason="海嘯事件缺少沿岸、港口或潮位脈絡，地理關係需要人工確認。",
                    evidence=chunk.summary,
                    node_id=chunk.id,
                )
            )
        if any(word in text for word in ["無災損", "未受損", "無明顯損害"]) and any(word in text for word in ["中斷", "倒塌", "沖毀", "受損"]):
            anomalies.append(
                Anomaly(
                    id=f"anom-{chunk.id}-contradiction",
                    severity="high",
                    score=0.92,
                    reason="同一段資料同時描述無災損與明確損害，存在語意矛盾。",
                    evidence=chunk.summary,
                    node_id=chunk.id,
                )
            )
        for metric in chunk.metrics:
            value_match = re.search(r"\d+(?:\.\d+)?", metric)
            if value_match:
                value = float(value_match.group(0))
                if ("mm" in metric or "毫米" in metric) and value >= 500:
                    anomalies.append(
                        Anomaly(
                            id=f"anom-{chunk.id}-{metric}",
                            severity="medium",
                            score=min(0.99, value / 900),
                            reason="雨量數值高於 baseline 閾值，建議比對測站與歷史分位數。",
                            evidence=f"{metric}；{chunk.summary}",
                            node_id=chunk.id,
                        )
                    )
        for hazard in chunk.hazards:
            for location in chunk.locations:
                if pair_counts[(hazard, location)] == 1 and hazard != "general":
                    anomalies.append(
                        Anomaly(
                            id=f"anom-{chunk.id}-{hazard}-{location}",
                            severity="low",
                            score=0.42,
                            reason="此災害類型與地點為目前圖譜中的低頻組合，可作為 GNN outlier 的候選樣本。",
                            evidence=chunk.summary,
                            node_id=chunk.id,
                        )
                    )
    unique = {item.id: item for item in anomalies}
    return sorted(unique.values(), key=lambda item: item.score, reverse=True)[:12]


def compose_answer(query: str, evidences: list[Evidence], anomalies: list[Anomaly]) -> str:
    if not evidences:
        return "目前知識庫沒有足夠證據回答此查詢。"
    lead = evidences[0]
    hazard_text = "、".join(sorted(set(h for evidence in evidences for h in evidence.hazards)))
    location_text = "、".join(sorted(set(l for evidence in evidences for l in evidence.locations))) or "未標明地點"
    anomaly_note = f"系統另偵測到 {len(anomalies)} 筆可能異常，建議優先複核高分項目。" if anomalies else "目前沒有偵測到高風險異常。"
    return (
        f"針對「{query}」，MoR Router 主要命中 {hazard_text} 類資料，關聯地點為 {location_text}。"
        f"最高分證據來自《{lead.title}》：{lead.text} {anomaly_note}"
    )
