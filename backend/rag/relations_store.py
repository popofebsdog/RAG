from __future__ import annotations

import json
import os
import re
import time
import uuid

from . import postgres_store

_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "relations_cache")


def _safe(name: str) -> str:
    return re.sub(r"[^\w\-.]", "_", name)


def _project_path(project_id: str) -> str:
    d = os.path.join(_BASE_DIR, _safe(project_id))
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "relations.json")


def _load(project_id: str) -> list[dict]:
    p = _project_path(project_id)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        raw = f.read().strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        return []
    except json.JSONDecodeError:
        # Try to recover from trailing-bracket corruption (e.g. "]]")
        while raw.endswith("]") and not raw.endswith("[]"):
            candidate = raw[: raw.rfind("]")]
            try:
                data = json.loads(candidate + "]")
                if isinstance(data, list):
                    _save(project_id, data)  # auto-repair
                    return data
            except json.JSONDecodeError:
                pass
            raw = candidate
        return []


def _save(project_id: str, data: list[dict]) -> None:
    with open(_project_path(project_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Public API ────────────────────────────────────────────────────────────────

def list_relations(project_id: str) -> list[dict]:
    if postgres_store.is_enabled():
        return postgres_store.list_relations(project_id)
    return _load(project_id)


def add_relation(
    from_chunk_id: str,
    to_chunk_id: str,
    label: str,
    project_id: str,
    weight: float = 1.0,
) -> dict:
    if postgres_store.is_enabled():
        return postgres_store.add_relation(from_chunk_id, to_chunk_id, label, project_id, weight)
    relations = _load(project_id)
    relation = {
        "id": str(uuid.uuid4()),
        "from_chunk_id": from_chunk_id,
        "to_chunk_id": to_chunk_id,
        "label": label,
        "weight": weight,
        "project_id": project_id,
        "created_at": int(time.time()),
    }
    relations.append(relation)
    _save(project_id, relations)
    return relation


def update_relation_weight(relation_id: str, weight: float, project_id: str) -> bool:
    if postgres_store.is_enabled():
        return postgres_store.update_relation_weight(relation_id, weight, project_id)
    relations = _load(project_id)
    for r in relations:
        if r["id"] == relation_id:
            r["weight"] = max(0.0, min(1.0, weight))
            _save(project_id, relations)
            return True
    return False


def remove_relation(relation_id: str, project_id: str) -> bool:
    if postgres_store.is_enabled():
        return postgres_store.remove_relation(relation_id, project_id)
    relations = _load(project_id)
    new = [r for r in relations if r["id"] != relation_id]
    if len(new) == len(relations):
        return False
    _save(project_id, new)
    return True


def clear_relations(project_id: str) -> None:
    if postgres_store.is_enabled():
        postgres_store.clear_relations(project_id)
        return
    _save(project_id, [])


def remove_relations_for_chunks(chunk_ids: set[str], project_id: str) -> list[str]:
    """Remove relations touching any chunk id and return removed relation ids."""
    if postgres_store.is_enabled():
        return postgres_store.remove_relations_for_chunks(chunk_ids, project_id)
    relations = _load(project_id)
    kept: list[dict] = []
    removed: list[str] = []
    for relation in relations:
        if relation["from_chunk_id"] in chunk_ids or relation["to_chunk_id"] in chunk_ids:
            removed.append(relation["id"])
        else:
            kept.append(relation)
    if removed:
        _save(project_id, kept)
    return removed
