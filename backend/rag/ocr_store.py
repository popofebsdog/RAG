from __future__ import annotations

import json
import os
import re

_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "ocr_cache")


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w\-.]", "_", name)


def _project_dir(project_id: str) -> str:
    d = os.path.join(_BASE_DIR, _safe_name(project_id))
    os.makedirs(d, exist_ok=True)
    return d


def _ocr_path(source_doc: str, project_id: str) -> str:
    return os.path.join(_project_dir(project_id), f"{_safe_name(source_doc)}.json")


def get_ocr(source_doc: str, project_id: str = "default") -> list[dict]:
    path = _ocr_path(source_doc, project_id)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def store_ocr(source_doc: str, pages: list[dict], project_id: str = "default") -> None:
    with open(_ocr_path(source_doc, project_id), "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False)


def remove_doc(source_doc: str, project_id: str = "default") -> None:
    path = _ocr_path(source_doc, project_id)
    if os.path.exists(path):
        os.unlink(path)


def clear(project_id: str = "default") -> None:
    d = _project_dir(project_id)
    if not os.path.exists(d):
        return
    for fname in os.listdir(d):
        fpath = os.path.join(d, fname)
        if os.path.isfile(fpath):
            os.unlink(fpath)
