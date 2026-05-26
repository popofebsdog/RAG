from __future__ import annotations

import json
import os
import re
import shutil
import time
from typing import Any

_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "graphs_cache")


def _safe(name: str) -> str:
    return re.sub(r"[^\w\-.]", "_", name or "default")


def _project_dir(project_id: str) -> str:
    d = os.path.join(_BASE_DIR, _safe(project_id))
    os.makedirs(d, exist_ok=True)
    return d


def save_graph(project_id: str, graph_name: str, data: dict[str, Any]) -> str:
    payload = {
        "graph_name": graph_name,
        "project_id": project_id,
        "updated_at": int(time.time()),
        "data": data,
    }
    path = os.path.join(_project_dir(project_id), f"{_safe(graph_name)}_latest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    return path


def clear_graphs(project_id: str) -> None:
    d = os.path.join(_BASE_DIR, _safe(project_id))
    if os.path.isdir(d):
        shutil.rmtree(d)


def list_graphs(project_id: str) -> list[dict[str, Any]]:
    d = _project_dir(project_id)
    items: list[dict[str, Any]] = []
    for filename in sorted(os.listdir(d)):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(d, filename)
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            payload = {}
        data = payload.get("data") if isinstance(payload, dict) else None
        items.append({
            "filename": filename,
            "graph_name": payload.get("graph_name", filename.removesuffix("_latest.json")) if isinstance(payload, dict) else filename,
            "updated_at": payload.get("updated_at") if isinstance(payload, dict) else int(os.path.getmtime(path)),
            "size_bytes": os.path.getsize(path),
            "node_count": _count_nodes(data),
            "edge_count": _count_edges(data),
        })
    return items


def read_graph(project_id: str, filename: str) -> dict[str, Any]:
    safe_filename = os.path.basename(filename)
    if safe_filename != filename or not safe_filename.endswith(".json"):
        raise FileNotFoundError(filename)
    path = os.path.join(_project_dir(project_id), safe_filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {"data": data}


def _count_nodes(data: Any) -> int:
    if isinstance(data, dict):
        nodes = data.get("nodes")
        points = data.get("points")
        if isinstance(nodes, list):
            return len(nodes)
        if isinstance(points, list):
            return len(points)
        inner = data.get("data")
        if inner is not data:
            return _count_nodes(inner)
    return 0


def _count_edges(data: Any) -> int:
    if isinstance(data, dict):
        edges = data.get("edges")
        relations = data.get("relations")
        if isinstance(edges, list):
            return len(edges)
        if isinstance(relations, list):
            return len(relations)
        inner = data.get("data")
        if inner is not data:
            return _count_edges(inner)
    return 0
