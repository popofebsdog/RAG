from __future__ import annotations

import base64
import json
import os
import re

_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "images_cache")


def _safe(name: str) -> str:
    return re.sub(r"[^\w\-.]", "_", name)


def _doc_dir(source_doc: str, project_id: str) -> str:
    d = os.path.join(_BASE_DIR, _safe(project_id), _safe(source_doc))
    os.makedirs(d, exist_ok=True)
    return d


def _meta_path(source_doc: str, project_id: str) -> str:
    return os.path.join(_doc_dir(source_doc, project_id), "_meta.json")


def _img_path(source_doc: str, project_id: str, page_num: int, image_index: int) -> str:
    return os.path.join(_doc_dir(source_doc, project_id), f"p{page_num}_i{image_index}.png")


# ── Public API ────────────────────────────────────────────────────────────────

def store_images(source_doc: str, images: list, project_id: str = "default") -> None:
    """Persist extracted PageImage list to disk."""
    from .loader import PageImage

    meta: list[dict] = []
    for img in images:
        png_bytes = base64.b64decode(img.data_b64)
        path = _img_path(source_doc, project_id, img.page_num, img.image_index)
        with open(path, "wb") as f:
            f.write(png_bytes)
        meta.append({
            "page_num": img.page_num,
            "image_index": img.image_index,
            "width": img.width,
            "height": img.height,
        })

    with open(_meta_path(source_doc, project_id), "w", encoding="utf-8") as f:
        json.dump(meta, f)


def get_images(source_doc: str, project_id: str = "default") -> list[dict]:
    """Return list of {page_num, image_index, data_b64, width, height}."""
    meta_file = _meta_path(source_doc, project_id)
    if not os.path.exists(meta_file):
        return []
    with open(meta_file, encoding="utf-8") as f:
        meta = json.load(f)

    result = []
    for m in meta:
        path = _img_path(source_doc, project_id, m["page_num"], m["image_index"])
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            data_b64 = base64.b64encode(f.read()).decode()
        result.append({
            "page_num": m["page_num"],
            "image_index": m["image_index"],
            "data_b64": data_b64,
            "width": m["width"],
            "height": m["height"],
        })
    return result


def remove_doc(source_doc: str, project_id: str = "default") -> None:
    import shutil
    d = _doc_dir(source_doc, project_id)
    if os.path.isdir(d):
        shutil.rmtree(d)


def clear(project_id: str = "default") -> None:
    import shutil
    d = os.path.join(_BASE_DIR, _safe(project_id))
    if os.path.isdir(d):
        shutil.rmtree(d)
