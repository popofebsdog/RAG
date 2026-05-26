from __future__ import annotations

import os
from dataclasses import dataclass

from .chunking import Chunk
from .embedding import embed_query
from .hazards import LEGACY_HAZARD_ALIASES, router_scores
from .qdrant_store import QdrantStore, relation_chunk_id
from .relations_store import list_relations

# Additive score boost applied to manual (user-annotated) chunks.
# Acts as supervised attention: chunks the user explicitly marked are
# always retrieved and ranked higher than a raw similarity score alone.
MANUAL_BOOST: float = float(os.getenv("MANUAL_BOOST", "0.15"))


@dataclass
class RetrievalResult:
    chunk: Chunk
    score: float
    is_boosted: bool = False   # True when manual-attention boost was applied


@dataclass
class RetrievalOutput:
    results: list[RetrievalResult]
    # Max auto-chunk similarity BEFORE boost — used by C1 out-of-domain detection.
    # None when no auto chunks exist in the collection.
    max_auto_score: float | None
    router: dict[str, float]


def retrieve(
    query: str,
    store: QdrantStore,
    top_k: int | None = None,
    region: str | None = None,
    year: int | None = None,
    project_id: str = "default",
) -> RetrievalOutput:
    top_k = top_k or int(os.getenv("TOP_K", 5))
    query_vec = embed_query(query)
    router = router_scores(query)

    # ── Auto chunks: fetch extra, filter manual chunks in Python ─────────────
    # Qdrant local mode doesn't reliably handle MatchValue(value=False) for booleans.
    all_hits = store.search(
        query_vec, top_k=(top_k * 2) + 20,  # overfetch to account for manual chunk removal
        region=region, year=year, project_id=project_id,
    )
    auto_hits = [(c, _hazard_adjusted_score(c, s, router, store)) for c, s in all_hits if not c.chunk_id.startswith("manual:") and not c.chunk_id.startswith("relation:")]

    # ── Manual chunks: always included, scored independently ─────────────────
    manual_hits = [
        (c, _hazard_adjusted_score(c, s, router, store))
        for c, s in store.search_manual(query_vec, project_id=project_id)
    ]

    # Track max auto score BEFORE merge (C1 needs this even if auto chunks
    # don't make it into the final top_k because manual chunks displaced them)
    max_auto_score: float | None = max((s for _, s in auto_hits), default=None)

    # ── Merge: manual chunks win if same chunk_id appears in both pools ───────
    seen: dict[str, RetrievalResult] = {}

    for chunk, score in auto_hits:
        seen[chunk.chunk_id] = RetrievalResult(chunk=chunk, score=score, is_boosted=False)

    for chunk, score in manual_hits:
        boosted = min(score + MANUAL_BOOST, 1.0)   # cap at 1.0 for display sanity
        seen[chunk.chunk_id] = RetrievalResult(chunk=chunk, score=boosted, is_boosted=True)

    _expand_relation_neighbors(seen, store, project_id)
    _expand_source_page_context(seen, store, project_id)

    results = sorted(seen.values(), key=lambda r: r.score, reverse=True)[:top_k]
    return RetrievalOutput(results=results, max_auto_score=max_auto_score, router=router)


def _hazard_adjusted_score(
    chunk: Chunk,
    score: float,
    router: dict[str, float],
    store: QdrantStore,
) -> float:
    payload = store.get_payload(chunk.chunk_id) or {}
    tags = payload.get("hazard_tags") or []
    if not tags:
        return score
    normalized_tags = [LEGACY_HAZARD_ALIASES.get(tag, tag) for tag in tags]
    hazard_boost = max((router.get(tag, 0.0) for tag in normalized_tags), default=0.0)
    weight = float(payload.get("weight", 1.0))
    return min(score + hazard_boost * 0.12, 1.0) * weight


def _expand_relation_neighbors(
    seen: dict[str, RetrievalResult],
    store: QdrantStore,
    project_id: str,
) -> None:
    """Use manual relation edges as supervised attention expansion.

    If a relation node or either endpoint is retrieved, pull in the linked
    neighbor with a score proportional to the relation weight.
    """
    for relation in list_relations(project_id):
        relation_id = relation["id"]
        relation_chunk = relation_chunk_id(relation_id)
        from_id = relation["from_chunk_id"]
        to_id = relation["to_chunk_id"]
        weight = float(relation.get("weight", 1.0))

        touched_score = max(
            seen.get(relation_chunk, RetrievalResult(Chunk("", "", 0, 0, 0), 0)).score,
            seen.get(from_id, RetrievalResult(Chunk("", "", 0, 0, 0), 0)).score,
            seen.get(to_id, RetrievalResult(Chunk("", "", 0, 0, 0), 0)).score,
        )
        if touched_score <= 0:
            continue

        for chunk_id in (from_id, to_id, relation_chunk):
            if chunk_id in seen:
                continue
            payload = store.get_payload(chunk_id)
            if not payload:
                continue
            chunk = Chunk(
                chunk_id=payload["chunk_id"],
                text=payload["text"],
                source_page=payload.get("source_page", 0),
                start_char=payload.get("start_char", 0),
                end_char=payload.get("end_char", 0),
                source_doc=payload.get("source_doc", ""),
                source_anchor=payload.get("source_anchor"),
            )
            seen[chunk_id] = RetrievalResult(
                chunk=chunk,
                score=min(touched_score * (0.72 + weight * 0.28), 1.0),
                is_boosted=True,
            )


def _expand_source_page_context(
    seen: dict[str, RetrievalResult],
    store: QdrantStore,
    project_id: str,
) -> None:
    """Add original page chunks for retrieved graph nodes.

    The graph nodes are intentionally concise, but answer generation needs the
    source paragraph around them. This is the L2 GraphRAG expansion: vector hit
    → graph/source anchor → original page context.
    """
    payloads = store.payloads_by_chunk_id(project_id=project_id)
    page_scores: dict[tuple[str, int], float] = {}
    for result in list(seen.values()):
        payload = payloads.get(result.chunk.chunk_id) or {}
        if payload.get("node_type") == "relation":
            continue
        if not payload.get("is_manual"):
            continue
        source_doc = str(payload.get("source_doc") or "")
        source_page = int(payload.get("source_page") or 0)
        if not source_doc or source_page <= 0:
            continue
        key = (source_doc, source_page)
        page_scores[key] = max(page_scores.get(key, 0.0), result.score)

    if not page_scores:
        return

    for payload in payloads.values():
        if payload.get("node_type") != "auto":
            continue
        key = (str(payload.get("source_doc") or ""), int(payload.get("source_page") or 0))
        touched_score = page_scores.get(key, 0.0)
        if touched_score <= 0:
            continue
        expanded_score = min(touched_score * 0.97, 0.99)
        existing = seen.get(payload["chunk_id"])
        if existing:
            if expanded_score > existing.score:
                existing.score = expanded_score
                existing.is_boosted = True
            continue
        chunk = Chunk(
            chunk_id=payload["chunk_id"],
            text=payload["text"],
            source_page=payload.get("source_page", 0),
            start_char=payload.get("start_char", 0),
            end_char=payload.get("end_char", 0),
            source_doc=payload.get("source_doc", ""),
            source_anchor=payload.get("source_anchor"),
        )
        seen[chunk.chunk_id] = RetrievalResult(
            chunk=chunk,
            score=expanded_score,
            is_boosted=True,
        )
