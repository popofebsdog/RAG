from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any, Iterable


def _dataset_split(source_key: str) -> str:
    bucket = int(hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < 80:
        return "train"
    if bucket < 90:
        return "validation"
    return "test"


def _index_by_id(items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in items}


def _changes(original: list[dict[str, Any]], reviewed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    original_by_id = _index_by_id(original)
    reviewed_by_id = _index_by_id(reviewed)
    changes: list[dict[str, Any]] = []

    for item_id in dict.fromkeys([*original_by_id, *reviewed_by_id]):
        before = original_by_id.get(item_id)
        after = reviewed_by_id.get(item_id)
        if before is None:
            status = "added"
        elif after is None or not bool(after.get("approved", True)):
            status = "rejected"
        elif before == after:
            status = "accepted"
        else:
            status = "modified"

        fields: dict[str, dict[str, Any]] = {}
        for key in set((before or {}).keys()) | set((after or {}).keys()):
            before_value = (before or {}).get(key)
            after_value = (after or {}).get(key)
            if before_value != after_value:
                fields[key] = {"before": before_value, "after": after_value}

        changes.append({"id": item_id, "status": status, "fields": fields})
    return changes


def build_review_sample(
    pending: dict[str, Any],
    reviewed_nodes: list[dict[str, Any]],
    reviewed_relations: list[dict[str, Any]],
    *,
    reviewer_id: str | None = None,
    review_notes: str | None = None,
    training_eligible: bool = True,
) -> dict[str, Any]:
    original_nodes = list(pending.get("nodes") or [])
    original_relations = list(pending.get("relations") or [])
    source_identity = pending.get("source_sha256") or pending.get("filename") or pending.get("preview_id") or ""
    source_key = f"{pending.get('project_id') or 'default'}:{source_identity}"
    return {
        "sample_id": str(uuid.uuid4()),
        "schema_version": "1.0",
        "project_id": str(pending.get("project_id") or "default"),
        "preview_id": str(pending.get("preview_id") or ""),
        "filename": str(pending.get("filename") or ""),
        "source_sha256": str(pending.get("source_sha256") or ""),
        "model_name": str(pending.get("model_name") or ""),
        "prompt_version": str(pending.get("prompt_version") or ""),
        "reviewer_id": (reviewer_id or "").strip() or None,
        "review_notes": (review_notes or "").strip() or None,
        "training_eligible": bool(training_eligible),
        "dataset_split": _dataset_split(source_key),
        "original": {"nodes": original_nodes, "relations": original_relations},
        "reviewed": {"nodes": reviewed_nodes, "relations": reviewed_relations},
        "changes": {
            "nodes": _changes(original_nodes, reviewed_nodes),
            "relations": _changes(original_relations, reviewed_relations),
        },
        "created_at": int(time.time()),
    }


def build_relation_review_sample(
    action: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    *,
    project_id: str,
    reviewer_id: str | None,
    review_notes: str | None = None,
    training_eligible: bool = True,
    model_name: str = "",
) -> dict[str, Any]:
    if action not in {"create", "update", "delete"}:
        raise ValueError("relation action must be create, update, or delete")
    event_id = str(uuid.uuid4())
    relation = after or before or {}
    original_relations = [before] if before else []
    if action == "delete" and before:
        reviewed_relations = [{**before, "approved": False}]
    else:
        reviewed_relations = [after] if after else []
    pending = {
        "preview_id": f"relation-event:{event_id}",
        "project_id": project_id,
        "filename": str(relation.get("source_doc") or "relation-edit"),
        "source_sha256": f"relation:{relation.get('id') or event_id}",
        "model_name": model_name,
        "prompt_version": "relation-review-v1",
        "nodes": [],
        "relations": original_relations,
    }
    sample = build_review_sample(
        pending,
        [],
        reviewed_relations,
        reviewer_id=reviewer_id,
        review_notes=review_notes,
        training_eligible=training_eligible,
    )
    sample["task_type"] = "relation_review"
    sample["action"] = action
    return sample


def export_sft_jsonl(samples: Iterable[dict[str, Any]]) -> str:
    rows: list[str] = []
    for sample in samples:
        if not sample.get("training_eligible"):
            continue
        user_payload = {
            "filename": sample.get("filename"),
            "source_sha256": sample.get("source_sha256"),
            "candidate_nodes": (sample.get("original") or {}).get("nodes", []),
            "candidate_relations": (sample.get("original") or {}).get("relations", []),
        }
        assistant_payload = sample.get("reviewed") or {"nodes": [], "relations": []}
        system_prompt = (
            "Review an engineering knowledge relation and return the approved relation state as JSON."
            if sample.get("task_type") == "relation_review"
            else "Review extracted engineering knowledge and return approved nodes and relations as JSON."
        )
        row = {
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, sort_keys=True)},
                {"role": "assistant", "content": json.dumps(assistant_payload, ensure_ascii=False, sort_keys=True)},
            ],
            "metadata": {
                key: sample.get(key)
                for key in (
                    "sample_id",
                    "project_id",
                    "filename",
                    "source_sha256",
                    "model_name",
                    "prompt_version",
                    "reviewer_id",
                    "dataset_split",
                    "task_type",
                    "action",
                )
            },
        }
        rows.append(json.dumps(row, ensure_ascii=False, sort_keys=True))
    return "\n".join(rows) + ("\n" if rows else "")
