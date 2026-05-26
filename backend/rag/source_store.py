from __future__ import annotations

import os
import re
import shutil

_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "source_cache")


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w\-.]", "_", name)


def _project_dir(project_id: str) -> str:
    d = os.path.join(_BASE_DIR, _safe_name(project_id))
    os.makedirs(d, exist_ok=True)
    return d


def _source_path(source_doc: str, project_id: str) -> str:
    return os.path.join(_project_dir(project_id), _safe_name(source_doc))


def store_pdf(source_doc: str, contents: bytes, project_id: str = "default") -> str:
    path = _source_path(source_doc, project_id)
    with open(path, "wb") as f:
        f.write(contents)
    return path


def get_pdf_path(source_doc: str, project_id: str = "default") -> str | None:
    path = _source_path(source_doc, project_id)
    if not os.path.exists(path):
        return None
    return path


def remove_doc(source_doc: str, project_id: str = "default") -> None:
    path = _source_path(source_doc, project_id)
    if os.path.exists(path):
        os.unlink(path)


def clear(project_id: str = "default") -> None:
    d = _project_dir(project_id)
    if os.path.exists(d):
        shutil.rmtree(d)
