from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

# Only run C2 LLM check when the question explicitly asserts causation.
_CAUSAL_RE = re.compile(
    r'導致|造成|因為|引起|由於|使得|所以|因此|才會|才導|引發|引致'
    r'|causes?|because|results?\s+in|due\s+to|leads?\s+to|trigger',
    re.IGNORECASE,
)

# Skip C2 if question is clearly interrogative (asking, not asserting).
# Matches: leading question words OR trailing question markers.
_QUESTION_RE = re.compile(
    r'^(什麼|哪些|哪種|哪個|為何|為什麼|如何|怎樣|怎麼|是否|有沒有|能否|請問)'
    r'|[嗎呢？?]$',
)

_DIRECTION_TERMS = {"南側", "北側", "東側", "西側", "左側", "右側", "上方", "下方", "上游", "下游"}

_DOMAIN_TERMS = {
    "災情", "災害", "崩塌", "山崩", "落石", "邊坡", "岩體", "岩層", "坡趾", "坡址",
    "傾覆", "倒懸", "破壞", "滑動", "土石流", "降雨", "雨量", "豪雨", "颱風",
    "地震", "斷層", "地質", "地形", "岩塊", "砂岩", "頁岩", "砂頁", "互層",
    "道路中斷", "災損",
}

_GEOLOGY_TERMS = {
    "地質", "地質條件", "地形", "岩層", "岩體", "岩塊", "砂岩", "頁岩", "砂頁",
    "互層", "地層", "坡面", "邊坡", "坡趾", "坡址", "風化", "破碎",
}

_QUERY_EXPANSIONS = {
    "災情": {"災害", "崩塌", "落石", "破壞", "災損"},
    "災害": {"災情", "崩塌", "落石", "破壞", "災損"},
    "山崩": {"崩塌", "災害"},
    "邊坡": {"坡面", "坡趾", "坡址"},
    "地質": {"地質條件", "岩層", "岩體", "砂岩", "頁岩", "砂頁", "互層", "地層"},
    "地質條件": {"地質", "岩層", "岩體", "砂岩", "頁岩", "砂頁", "互層", "地層"},
    "岩層": {"地質", "地質條件", "砂岩", "頁岩", "砂頁", "互層", "地層"},
    "坡趾": {"坡址"},
    "坡址": {"坡趾"},
}


@dataclass
class AnomalyFlagData:
    type: str   # "out_of_domain" | "insufficient_evidence" | "relation_contradiction"
    message: str
    details: dict = field(default_factory=dict)


@dataclass
class EvidenceSupport:
    supported: bool
    score: float
    reason: str
    query_terms: set[str] = field(default_factory=set)
    matched_terms: set[str] = field(default_factory=set)
    missing_directions: set[str] = field(default_factory=set)


def detect_out_of_domain(
    max_auto_score: Optional[float],
    threshold: float = 0.60,
    question: str | None = None,
    retrieved: list[dict] | None = None,
) -> Optional[AnomalyFlagData]:
    """C1: highest auto-chunk similarity below threshold → query is out-of-domain.

    Receives the pre-computed max auto-chunk score so that manual chunks
    displacing auto chunks from top_k does not mask out-of-domain queries.
    Returns None when there are no auto chunks (can't determine domain).
    """
    if max_auto_score is None:
        return None
    if max_auto_score < threshold:
        if question and retrieved:
            support = evidence_support(question, retrieved)
            has_domain_intent = bool(support.query_terms & _DOMAIN_TERMS)
            if support.supported or support.reason == "direction_mismatch" or has_domain_intent:
                return None
        return AnomalyFlagData(
            type="out_of_domain",
            message="查詢語意與目前知識庫主題不相符",
            details={"max_score": round(max_auto_score, 4), "threshold": threshold},
        )
    return None


def detect_graph_out_of_domain(
    question: str,
    retrieved: list[dict],
    router: dict[str, float],
    threshold: float = 0.64,
) -> Optional[AnomalyFlagData]:
    """C1b: graph/manual-only support gap detection.

    Manual nodes are intentionally boosted, so score alone is not reliable.
    This check is about evidence support, not broad domain membership. We flag
    only when both signals are weak:
    1. hazard router is almost uniform, meaning no hazard route clearly matches;
       and
    2. the query has little direct lexical overlap with retrieved node labels
       and text snippets.
    """
    if not retrieved:
        return AnomalyFlagData(
            type="out_of_domain",
            message="查詢語意與目前知識庫主題不相符",
            details={"reason": "no_retrieved_chunks"},
        )

    if router:
        scores = list(router.values())
        router_spread = max(scores) - min(scores)
    else:
        router_spread = 0.0

    support = evidence_support(question, retrieved)
    if support.supported:
        return None

    if support.reason == "no_query_terms":
        return None

    has_domain_intent = bool(support.query_terms & _DOMAIN_TERMS)
    if has_domain_intent:
        return None

    if router_spread <= 0.03 and support.score < threshold:
        return AnomalyFlagData(
            type="out_of_domain",
            message="查詢語意與目前知識庫主題不相符",
            details={
                "keyword_overlap": round(support.score, 4),
                "threshold": threshold,
                "router_spread": round(router_spread, 4),
                "query_tokens": sorted(support.query_terms)[:20],
                "matched_terms": sorted(support.matched_terms)[:20],
            },
        )
    return None


def evidence_support(question: str, retrieved: list[dict], threshold: float = 0.18) -> EvidenceSupport:
    """Return whether retrieved chunks visibly support the query's entities.

    This is intentionally lexical and conservative. It prevents false anomaly
    flags for exact entities such as 「平浪橋南側」 even when dense-vector scores
    are just below a global threshold.
    """
    query_terms = _domain_tokens(question, expand=True)
    if not query_terms:
        return EvidenceSupport(False, 0.0, "no_query_terms")

    corpus = " ".join(
        str(item.get("label") or "") + " " + str(item.get("text") or "")
        for item in retrieved
    )
    corpus_terms = _domain_tokens(corpus, expand=False)
    if not corpus_terms:
        return EvidenceSupport(False, 0.0, "no_corpus_terms", query_terms=query_terms)

    matched_terms = query_terms & corpus_terms
    direction_terms = {term for term in _DIRECTION_TERMS if term in question}
    corpus_directions = {term for term in _DIRECTION_TERMS if term in corpus}
    missing_directions = direction_terms - corpus_directions
    if missing_directions and not matched_terms:
        return EvidenceSupport(
            False,
            len(matched_terms) / max(len(query_terms), 1),
            "direction_mismatch",
            query_terms=query_terms,
            matched_terms=matched_terms,
            missing_directions=missing_directions,
        )

    score = len(matched_terms) / max(len(query_terms), 1)
    has_named_entity = any(len(term) >= 3 and term not in _DOMAIN_TERMS for term in matched_terms)
    has_domain_match = bool(matched_terms & _DOMAIN_TERMS)
    query_has_domain = bool(query_terms & _DOMAIN_TERMS)
    corpus_has_domain = bool(corpus_terms & _DOMAIN_TERMS)
    geology_query = bool(query_terms & _GEOLOGY_TERMS)
    geology_corpus = bool(corpus_terms & _GEOLOGY_TERMS)
    supported = (
        score >= threshold
        or has_named_entity
        or (has_domain_match and query_has_domain)
        or (query_has_domain and corpus_has_domain and bool(matched_terms))
        or (geology_query and geology_corpus)
    )
    return EvidenceSupport(
        supported,
        score,
        "supported" if supported else "weak_overlap",
        query_terms=query_terms,
        matched_terms=matched_terms,
    )


def _domain_tokens(text: str, *, expand: bool = False) -> set[str]:
    lowered = text.lower()
    tokens = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_+\-.]{1,}|[0-9]+(?:\.[0-9]+)?(?:mm|k|km|m|hr)?", lowered))
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        tokens.add(run)
        max_n = min(5, len(run))
        for n in range(2, max_n + 1):
            tokens.update(run[i:i + n] for i in range(0, len(run) - n + 1))
    tokens.update(term for term in _DOMAIN_TERMS if term in text)
    tokens.update(term for term in _DIRECTION_TERMS if term in text)
    if expand:
        for term, expansions in _QUERY_EXPANSIONS.items():
            if term in tokens or term in text:
                tokens.update(expansions)
    stopwords = {
        "什麼", "是否", "如何", "怎麼", "以及", "關係", "影響", "受到",
        "可以", "會不會", "有沒有", "多少", "多少錢", "一碗", "the", "and",
        "with", "what", "does",
    }
    return {token for token in tokens if token not in stopwords and len(token) >= 2}


def detect_relation_contradiction(
    question: str,
    enriched_relations: list[dict],
) -> Optional[AnomalyFlagData]:
    """C2: LLM check — does the question's causal claim contradict known manual relations?

    enriched_relations: list of dicts with keys:
        from_chunk_id, to_chunk_id, label, from_text (optional), to_text (optional)
    """
    if not enriched_relations:
        return None

    # Pre-filter 1: skip if no causal language
    if not _CAUSAL_RE.search(question):
        return None
    # Pre-filter 2: skip if question is interrogative (asking for causes, not asserting wrong ones)
    if _QUESTION_RE.search(question):
        return None

    relation_lines: list[str] = []
    for i, r in enumerate(enriched_relations, 1):
        # Prefer human-readable label names over raw chunk text
        from_name = (r.get("from_label") or r.get("from_text") or r.get("from_chunk_id", "?"))[:40].strip()
        to_name   = (r.get("to_label")   or r.get("to_text")   or r.get("to_chunk_id",   "?"))[:40].strip()
        edge_label = r.get("label", "→")
        relation_lines.append(f"{i}. 「{from_name}」 --[{edge_label}]--> 「{to_name}」")

    relations_str = "\n".join(relation_lines)

    prompt = f"""你是因果一致性檢查工具。

已知關係（共 {len(enriched_relations)} 條）：
{relations_str}

使用者提問：「{question}」

你的任務：判斷這個問題是否「斷言」了一個與已知關係方向相反的因果事實。

必須同時滿足以下兩個條件才能回傳 true：
1. 問題是一個【陳述句/斷言句】，而非疑問句。例如「X 造成 Y」是斷言，「什麼造成 Y？」「X 為何導致 Y？」是疑問，不算。
2. 斷言的因果方向與已知關係中某條明確相反（例如已知「雨量→災害」，但問題說「災害→雨量」）。

不確定時一律回傳 false。

僅回傳 JSON，不要有任何其他文字：
{{
  "has_contradiction": false,
  "explanation": "",
  "contradicted_relation_index": null
}}"""

    try:
        import os, httpx as _httpx

        provider = os.getenv("LLM_PROVIDER", "ollama")
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
        else:
            ollama_url   = os.getenv("OLLAMA_URL",   "http://localhost:11434")
            ollama_model = os.getenv("OLLAMA_MODEL",  "llama3.2")
            resp = _httpx.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": ollama_model,
                    "stream": False,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60,
            )
            resp.raise_for_status()
            raw = resp.json()["message"]["content"].strip()

        # Strip markdown code fence if model wraps it
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
    except Exception:
        return None

    if not data.get("has_contradiction"):
        return None

    idx = data.get("contradicted_relation_index")
    contradicted = enriched_relations[idx - 1] if idx and 1 <= idx <= len(enriched_relations) else None

    return AnomalyFlagData(
        type="relation_contradiction",
        message=f"因果矛盾：{data.get('explanation', '問題主張與知識庫關係矛盾')}",
        details={
            "explanation": data.get("explanation", ""),
            "contradicted_relation": contradicted,
        },
    )
