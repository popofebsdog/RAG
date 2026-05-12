from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Chunk, DocumentRecord

STORE_PATH = Path(__file__).resolve().parents[1] / "data" / "store.json"


def empty_store() -> dict[str, Any]:
    return {"documents": [], "chunks": []}


def load_store() -> dict[str, Any]:
    if not STORE_PATH.exists():
        return empty_store()
    return json.loads(STORE_PATH.read_text(encoding="utf-8"))


def save_store(data: dict[str, Any]) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_document(document: DocumentRecord, chunks: list[Chunk]) -> None:
    data = load_store()
    data["documents"] = [d for d in data["documents"] if d["id"] != document.id]
    data["chunks"] = [c for c in data["chunks"] if c["document_id"] != document.id]
    data["documents"].append(document.model_dump())
    data["chunks"].extend(chunk.model_dump() for chunk in chunks)
    save_store(data)


def all_chunks() -> list[Chunk]:
    return [Chunk(**item) for item in load_store()["chunks"]]


def all_documents() -> list[DocumentRecord]:
    return [DocumentRecord(**item) for item in load_store()["documents"]]


def reset_store() -> None:
    save_store(empty_store())
