from __future__ import annotations

import json
import os
import re

from .loader import PageContent

_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "pages_cache")


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w\-.]", "_", name)


def _project_dir(project_id: str) -> str:
    d = os.path.join(_BASE_DIR, _safe_name(project_id))
    os.makedirs(d, exist_ok=True)
    return d


def _page_path(source_doc: str, project_id: str) -> str:
    return os.path.join(_project_dir(project_id), f"{_safe_name(source_doc)}.json")


def _manifest_path(project_id: str) -> str:
    return os.path.join(_project_dir(project_id), "_manifest.json")


def _read_manifest(project_id: str) -> list[str]:
    p = _manifest_path(project_id)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _write_manifest(project_id: str, docs: list[str]) -> None:
    with open(_manifest_path(project_id), "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False)


# ── Public API ────────────────────────────────────────────────────────────────

def store_pages(source_doc: str, pages: list[PageContent], project_id: str = "default") -> None:
    data = [{"page_num": p.page_num, "text": p.text} for p in pages]
    with open(_page_path(source_doc, project_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    docs = _read_manifest(project_id)
    if source_doc not in docs:
        docs.append(source_doc)
        _write_manifest(project_id, docs)


def get_pages(source_doc: str, project_id: str = "default") -> list[dict]:
    p = _page_path(source_doc, project_id)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def list_docs(project_id: str = "default") -> list[str]:
    return _read_manifest(project_id)


def remove_doc(source_doc: str, project_id: str = "default") -> None:
    p = _page_path(source_doc, project_id)
    if os.path.exists(p):
        os.unlink(p)
    docs = _read_manifest(project_id)
    if source_doc in docs:
        docs.remove(source_doc)
        _write_manifest(project_id, docs)


def clear(project_id: str = "default") -> None:
    d = _project_dir(project_id)
    for fname in os.listdir(d):
        fpath = os.path.join(d, fname)
        if os.path.isfile(fpath):
            os.unlink(fpath)
