from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

import httpx

from .loader import PageContent
from .standardization import normalize_label, normalize_relation_label, normalize_text, standardize_relation_weight


LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))
KG_EXTRACTION_TIMEOUT = float(os.getenv("KG_EXTRACTION_TIMEOUT", "18"))
KG_EXTRACTION_USE_LLM = os.getenv("KG_EXTRACTION_USE_LLM", "1") != "0"


@dataclass
class ExtractedNode:
    label: str
    text: str
    page: int = 0


@dataclass
class ExtractedRelation:
    from_label: str
    to_label: str
    label: str
    weight: float = 0.75


@dataclass
class ExtractedKnowledgeGraph:
    nodes: list[ExtractedNode] = field(default_factory=list)
    relations: list[ExtractedRelation] = field(default_factory=list)


def extract_knowledge_graph(pages: list[PageContent], source_doc: str) -> ExtractedKnowledgeGraph:
    """Extract stable concept nodes and causal/semantic relations from a document.

    Uses the configured LLM provider when available, then falls back to a
    deterministic passage extractor so ingestion remains usable offline.
    """
    structured_graph = _extract_structured_vlm_markdown(pages)
    if _is_usable_graph(structured_graph):
        return structured_graph

    document = _compact_document(pages)
    if KG_EXTRACTION_USE_LLM:
        try:
            graph = _extract_with_llm(document, source_doc)
            if _is_usable_graph(graph):
                return graph
        except Exception:
            pass
    return _fallback_extract(pages)


def _extract_structured_vlm_markdown(pages: list[PageContent]) -> ExtractedKnowledgeGraph:
    nodes: list[ExtractedNode] = []
    relations: list[ExtractedRelation] = []
    labels_seen: set[str] = set()

    def ensure_node(label: str, evidence: str, page_num: int) -> str:
        clean_label = normalize_label(label, evidence)
        page_text = page_text_by_num.get(page_num, "")
        clean_text = _compose_vlm_node_text(page_text, clean_label, evidence or label)
        if not clean_label:
            return ""
        if _is_administrative_node(clean_label, clean_text):
            return ""
        if clean_label not in labels_seen:
            labels_seen.add(clean_label)
            nodes.append(ExtractedNode(label=clean_label, text=clean_text[:420], page=page_num))
        return clean_label

    page_text_by_num = {page.page_num: page.text for page in pages}
    for page in pages:
        for line in page.text.splitlines():
            stripped = line.strip().lstrip("-").strip()
            if not stripped:
                continue

            node_match = re.search(r"label\s*[:：]\s*(.+?)(?:\s*\|\s*evidence\s*[:：]\s*(.+))?$", stripped, flags=re.I)
            if node_match:
                label = node_match.group(1).strip()
                evidence = (node_match.group(2) or label).strip()
                ensure_node(label, evidence, page.page_num)
                continue

            rel_match = re.search(
                r"from\s*[:：]\s*(.+?)\s*\|\s*relation\s*[:：]\s*(.+?)\s*\|\s*to\s*[:：]\s*(.+?)(?:\s*\|\s*evidence\s*[:：]\s*(.+))?$",
                stripped,
                flags=re.I,
            )
            if rel_match:
                from_label_raw = rel_match.group(1).strip()
                relation_raw = rel_match.group(2).strip()
                to_label_raw = rel_match.group(3).strip()
                evidence = (rel_match.group(4) or stripped).strip()
                from_label = ensure_node(from_label_raw, evidence, page.page_num)
                to_label = ensure_node(to_label_raw, evidence, page.page_num)
                relation_label = normalize_relation_label(relation_raw)
                if from_label and to_label and from_label != to_label:
                    relations.append(ExtractedRelation(
                        from_label=from_label,
                        to_label=to_label,
                        label=relation_label,
                        weight=standardize_relation_weight(relation_label, 0.82),
                    ))

    unique_relations: list[ExtractedRelation] = []
    relation_keys: set[tuple[str, str, str]] = set()
    for rel in relations:
        key = (rel.from_label, rel.to_label, rel.label)
        if key in relation_keys:
            continue
        relation_keys.add(key)
        unique_relations.append(rel)
    return ExtractedKnowledgeGraph(nodes=nodes[:60], relations=unique_relations[:80])


def _compose_vlm_node_text(page_text: str, label: str, evidence: str) -> str:
    """Use the richer VLM page interpretation as node content, not chunk/anchor text."""
    clean_evidence = normalize_text(_strip_vlm_prefix(evidence))
    relevant_lines: list[str] = []
    for section in ["關鍵事實", "圖像證據", "數值與位置", "頁面摘要"]:
        for line in _section_lines(page_text, section):
            line = normalize_text(_strip_vlm_prefix(line))
            if not line or line == "無":
                continue
            if _line_matches_node(line, label, clean_evidence) or len(relevant_lines) < 2:
                relevant_lines.append(line)
            if len(relevant_lines) >= 5:
                break
        if len(relevant_lines) >= 5:
            break

    if clean_evidence and not _looks_like_weak_evidence(clean_evidence):
        relevant_lines.insert(0, clean_evidence)

    deduped: list[str] = []
    seen: set[str] = set()
    for line in relevant_lines:
        compact = re.sub(r"\s+", "", line)
        if compact in seen:
            continue
        seen.add(compact)
        deduped.append(line)
    text = "；".join(deduped[:5]) or clean_evidence or normalize_text(label)
    return text[:520]


def _section_lines(markdown: str, heading: str) -> list[str]:
    lines = markdown.splitlines()
    in_section = False
    result: list[str] = []
    for raw in lines:
        line = raw.strip()
        if re.match(r"^#{2,4}\s+", line):
            in_section = heading in line
            continue
        if in_section:
            if not line:
                continue
            if line.startswith("-"):
                result.append(line.lstrip("-").strip())
    return result


def _strip_vlm_prefix(text: str) -> str:
    value = re.sub(r"\^p\d+(?:-[\w\u4e00-\u9fff-]+)*", "", text or "")
    value = re.sub(r"\b(?:image|observation|implication|label|evidence)\s*[:：]", "", value, flags=re.I)
    value = value.replace("|", "，")
    return value.strip(" -，,。；;")


def _line_matches_node(line: str, label: str, evidence: str) -> bool:
    tokens = set(re.findall(r"[A-Za-z0-9.]+|[\u4e00-\u9fff]{2,}", f"{label} {evidence}"))
    if not tokens:
        return False
    return any(token in line for token in tokens)


def _looks_like_weak_evidence(text: str) -> bool:
    weak_phrases = [
        "報告標題", "聲明", "報告用途", "計畫資源", "技術支持", "分析流程",
        "聚焦", "強調", "頁面摘要", "本頁", "討論",
    ]
    return len(text) < 18 or any(phrase in text for phrase in weak_phrases)


def _is_administrative_node(label: str, evidence: str) -> bool:
    """Filter report/team/acknowledgement artifacts from the domain graph."""
    text = f"{label} {evidence}"
    generic_labels = {
        "報告",
        "本報告",
        "GeoPORT計畫",
        "報告調查與分析",
        "崩塌災害現象科學討論",
        "科學上的崩塌災害現象討論",
    }
    org_keywords = [
        "大學", "研究員", "教授", "博士", "團隊", "成員", "材料系", "土木系",
        "防災中心", "工程分局", "公路局", "特別感謝", "引用", "註明出處",
        "科學討論", "責任問題", "計畫名稱", "項目說明", "GeoPORT",
        "數位科技", "防災系統", "防災預警系統", "報告日期",
        "初勘報告", "報告完成", "NSTC", "團隊成員介紹", "調查能力",
        "遙測分析", "實地調查能力",
    ]
    domain_keywords = [
        "崩塌", "落石", "邊坡", "岩層", "岩體", "雨量", "降雨", "地質",
        "層理", "坡趾", "傾覆", "座標", "台2線", "70.1k", "70k",
        "土石流", "滑動", "破壞", "災害日期", "累積",
    ]
    weak_admin_phrases = [
        "報告標題", "聲明", "報告用途", "計畫資源", "技術支持", "分析流程",
        "團隊", "討論用途", "頁面摘要",
    ]
    if label in generic_labels:
        return True
    if any(phrase in text for phrase in weak_admin_phrases):
        return True
    if any(keyword in label for keyword in ["GeoPORT", "數位科技", "防災系統", "防災預警系統", "報告日期", "初勘報告", "本報告", "調查能力", "遙測分析"]):
        return True
    if any(keyword in text for keyword in org_keywords):
        return not any(keyword in text for keyword in domain_keywords)
    return False


def _extract_with_llm(document: str, source_doc: str) -> ExtractedKnowledgeGraph:
    system = (
        "你是地工災害文件的知識圖譜抽取器。"
        "請只根據文件內容，抽取穩定、可供後續比對的關鍵段落節點與關係。"
        "節點應是具體事實、地點、地質條件、雨量條件、破壞機制或結果。"
        "關係應是明確方向，例如：導致、促成、形成、觸發、影響、具有條件。"
        "不要加入文件沒有說的推測。"
    )
    user = f"""來源文件：{source_doc}

請從下列文件抽取知識圖譜。限制：
- nodes 最多 12 個。
- relations 最多 16 條。
- label 使用 6 到 24 個中文字，能作為圖上節點名稱。
- text 是完整佐證句，保留數值、地名、層位、時間。
- relation 的 from_label/to_label 必須完全對應 nodes 裡的 label。
- weight 介於 0.4 到 1.0，明確因果可高一些。
- 只輸出 JSON，不要 markdown，不要解釋。

JSON 格式：
{{
  "nodes": [
    {{"label": "...", "text": "...", "page": 1}}
  ],
  "relations": [
    {{"from_label": "...", "to_label": "...", "label": "導致", "weight": 0.9}}
  ]
}}

文件內容：
{document}
"""
    raw = _chat(system, user)
    data = _parse_json(raw)
    nodes = [
        ExtractedNode(
            label=normalize_label(str(item.get("label", "")), str(item.get("text", ""))),
            text=normalize_text(str(item.get("text", "")).strip()),
            page=int(item.get("page") or 0),
        )
        for item in data.get("nodes", [])
        if normalize_label(str(item.get("label", "")), str(item.get("text", ""))) and str(item.get("text", "")).strip()
    ]
    known = {node.label for node in nodes}
    relations = [
        ExtractedRelation(
            from_label=normalize_label(str(item.get("from_label", ""))),
            to_label=normalize_label(str(item.get("to_label", ""))),
            label=normalize_relation_label(str(item.get("label", ""))),
            weight=standardize_relation_weight(
                str(item.get("label", "")),
                max(0.0, min(1.0, float(item.get("weight") or 0.75))),
            ),
        )
        for item in data.get("relations", [])
    ]
    relations = [
        rel for rel in relations
        if rel.from_label in known and rel.to_label in known and rel.from_label != rel.to_label and rel.label
    ]
    return ExtractedKnowledgeGraph(nodes=nodes[:12], relations=relations[:16])


def _chat(system: str, user: str) -> str:
    if LLM_PROVIDER == "anthropic":
        import anthropic
        client = anthropic.Anthropic()
        message = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text

    resp = httpx.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=min(OLLAMA_TIMEOUT, KG_EXTRACTION_TIMEOUT),
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        text = match.group(0)
    data = json.loads(text)
    return data if isinstance(data, dict) else {}


def _compact_document(pages: list[PageContent]) -> str:
    parts: list[str] = []
    budget = int(os.getenv("KG_EXTRACTION_CHAR_BUDGET", "9000"))
    used = 0
    for page in pages:
        text = re.sub(r"\s+", " ", page.text).strip()
        if not text:
            continue
        block = f"[p.{page.page_num}] {text}"
        remaining = budget - used
        if remaining <= 0:
            break
        parts.append(block[:remaining])
        used += len(block[:remaining])
    return "\n\n".join(parts)


def _fallback_extract(pages: list[PageContent]) -> ExtractedKnowledgeGraph:
    candidates: list[ExtractedNode] = []
    relations: list[ExtractedRelation] = []

    def ensure_node(label: str, text: str, page: int) -> None:
        text = normalize_text(re.sub(r"\s+", " ", text).strip())
        label = normalize_label(label, text)
        if not label or any(node.label == label for node in candidates):
            return
        candidates.append(ExtractedNode(label=label, text=text[:420] or label, page=page))

    for page in pages:
        text = re.sub(r"\s+", " ", page.text)
        for match in re.finditer(r"node-[a-zA-Z0-9]+[：:]\s*([^。；\n]+)", text):
            content = match.group(1).strip()
            ensure_node(_make_label(content), content, page.page_num)

        for sentence in re.split(r"[。；\n]", text):
            if "->" not in sentence and "→" not in sentence:
                continue
            clean_parts: list[str] = []
            for clause in re.split(r"[，,]", sentence):
                if "->" not in clause and "→" not in clause:
                    continue
                parts = [_clean_arrow_endpoint(part) for part in re.split(r"->|→", clause)]
                parts = [normalize_label(part, sentence) for part in parts if part]
                parts = [part for part in parts if 2 <= len(part) <= 32]
                for part in parts:
                    if part not in clean_parts:
                        clean_parts.append(part)
                for a, b in zip(parts, parts[1:]):
                    if a != b:
                        relations.append(ExtractedRelation(a, b, normalize_relation_label("導致"), 0.82))
            for part in clean_parts:
                ensure_node(part, sentence.strip(), page.page_num)

    for page in pages:
        segments = re.split(r"(?<=[。！？.!?])\s+|\n+", page.text)
        for segment in segments:
            text = re.sub(r"\s+", " ", segment).strip()
            if len(text) < 24:
                continue
            if not _is_informative(text):
                continue
            label = normalize_label(_make_label(text), text)
            if not label:
                continue
            ensure_node(label, text, page.page_num)
            if len(candidates) >= 10:
                break
        if len(candidates) >= 10:
            break

    if len(relations) < 3:
        for prev, curr in zip(candidates, candidates[1:]):
            if any(rel.from_label == prev.label and rel.to_label == curr.label for rel in relations):
                continue
            label = _infer_relation_label(prev.text + curr.text)
            if label:
                relations.append(ExtractedRelation(
                    prev.label,
                    curr.label,
                    normalize_relation_label(label),
                    standardize_relation_weight(label, 0.68),
                ))
    return ExtractedKnowledgeGraph(nodes=candidates, relations=relations)


def _is_usable_graph(graph: ExtractedKnowledgeGraph) -> bool:
    if len(graph.nodes) < 2 or not graph.relations:
        return False
    useful_nodes = [
        node for node in graph.nodes
        if len(node.text.strip()) >= 16 and not re.fullmatch(r"node-[a-zA-Z0-9]+|[0-9.]+\s*mm", node.text.strip())
    ]
    return len(useful_nodes) >= 2


def _is_informative(text: str) -> bool:
    keywords = [
        "導致", "造成", "形成", "促成", "影響", "觸發", "崩塌", "滑動", "破壞",
        "雨量", "降雨", "地質", "岩體", "節理", "裂縫", "邊坡", "土石流", "落石",
    ]
    return any(keyword in text for keyword in keywords)


def _make_label(text: str) -> str:
    text = re.sub(r"^[#\-\d.、\s]+", "", text)
    for splitter in ["，", "。", "；", ":", "：", "，", ","]:
        if splitter in text:
            text = text.split(splitter)[0]
            break
    return text[:24]


def _clean_arrow_endpoint(text: str) -> str:
    value = re.sub(r"\s+", " ", text or "").strip()
    if "」" in value:
        value = value.split("」")[0]
    if "「" in value:
        value = value.split("「")[-1]
    value = re.split(r"[：:]", value)[-1]
    value = re.sub(r"^(建議|relation|關係|以及|並且|且|與)\s*", "", value, flags=re.I)
    return value.strip(" ：:，,。；;「」\"'")


def _infer_relation_label(text: str) -> str:
    if any(word in text for word in ["導致", "造成", "引發", "觸發"]):
        return "導致"
    if any(word in text for word in ["形成", "發展"]):
        return "形成"
    if any(word in text for word in ["影響", "促成"]):
        return "影響"
    return "關聯"
