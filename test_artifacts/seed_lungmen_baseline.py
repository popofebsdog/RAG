from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request


BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PROJECT_ID = "proj_1778639365155"
SOURCE_DOC = "龍門穩定基準圖譜"


NODES = [
    {
        "label": "龍門測區",
        "text": "龍門測區位於山坡地聚落上方，既有道路切坡與自然排水溝交會，作為後續降雨、地質與崩塌判斷的基準地點。",
        "region": "龍門",
        "perspective": "baseline",
    },
    {
        "label": "龍門月平均雨量 280 mm",
        "text": "龍門測區長期月平均雨量約 280 mm；若連續降雨使當月累積雨量明顯高於此基準，前期含水量通常偏高。",
        "region": "龍門",
        "perspective": "baseline_rainfall",
    },
    {
        "label": "歷史崩塌觸發雨量 520 mm/24h",
        "text": "龍門測區過去崩塌案例顯示，24 小時累積雨量接近或超過 520 mm 時，淺層崩塌風險快速上升；此數值應作為事件雨量的比較門檻。",
        "region": "龍門",
        "perspective": "baseline_threshold",
    },
    {
        "label": "破碎砂頁岩互層與順向坡",
        "text": "龍門測區地質以破碎砂頁岩互層與局部順向坡為主，節理發達、風化層厚度不均，降雨入滲後容易沿弱面累積孔隙水壓。",
        "region": "龍門",
        "perspective": "baseline_geology",
    },
    {
        "label": "前期含水量偏高",
        "text": "月累積雨量高於長期平均時，坡體前期含水量偏高，會降低後續短延時強降雨觸發崩塌所需的雨量門檻。",
        "region": "龍門",
        "perspective": "baseline_condition",
    },
    {
        "label": "孔隙水壓上升",
        "text": "強降雨進入破碎岩層與風化土層後，地下水位與孔隙水壓上升，有效應力下降，剪力強度隨之降低。",
        "region": "龍門",
        "perspective": "baseline_mechanism",
    },
    {
        "label": "邊坡穩定性下降",
        "text": "孔隙水壓上升與剪力強度降低會使邊坡穩定性下降；若同時存在順向坡或道路切坡，失穩機率更高。",
        "region": "龍門",
        "perspective": "baseline_mechanism",
    },
    {
        "label": "淺層崩塌發生",
        "text": "當事件雨量高於歷史觸發門檻，且地質弱面、前期含水量與孔隙水壓條件同時成立時，龍門測區可能發生淺層崩塌。",
        "region": "龍門",
        "perspective": "baseline_outcome",
    },
]


RELATIONS = [
    ("龍門測區", "龍門月平均雨量 280 mm", "具有雨量基準", 1.00),
    ("龍門測區", "破碎砂頁岩互層與順向坡", "具有地質條件", 1.00),
    ("龍門月平均雨量 280 mm", "前期含水量偏高", "高於基準導致", 0.82),
    ("前期含水量偏高", "歷史崩塌觸發雨量 520 mm/24h", "降低有效門檻", 0.72),
    ("破碎砂頁岩互層與順向坡", "孔隙水壓上升", "促進入滲導致", 0.88),
    ("歷史崩塌觸發雨量 520 mm/24h", "孔隙水壓上升", "超過門檻導致", 0.90),
    ("孔隙水壓上升", "邊坡穩定性下降", "導致", 0.95),
    ("邊坡穩定性下降", "淺層崩塌發生", "導致", 0.95),
    ("歷史崩塌觸發雨量 520 mm/24h", "淺層崩塌發生", "觸發風險", 0.86),
]


def request(method: str, path: str, payload: dict | None = None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE_URL + path, data=data, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else None


def get_json(path: str):
    with urllib.request.urlopen(BASE_URL + path, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def ensure_node(project_id: str, spec: dict, existing: dict[str, dict]) -> dict:
    if spec["label"] in existing:
        return existing[spec["label"]]
    payload = {
        "label": spec["label"],
        "text": spec["text"],
        "source_doc": SOURCE_DOC,
        "project_id": project_id,
        "region": spec["region"],
        "year": 2025,
        "perspective": spec["perspective"],
    }
    node = request("POST", "/chunks/manual", payload)
    existing[spec["label"]] = node
    return node


def ensure_relation(project_id: str, from_id: str, to_id: str, label: str, weight: float, existing: list[dict]) -> dict | None:
    for relation in existing:
        if (
            relation.get("from_chunk_id") == from_id
            and relation.get("to_chunk_id") == to_id
            and str(relation.get("label", "")).strip().casefold() == label.strip().casefold()
        ):
            return relation
    payload = {
        "from_chunk_id": from_id,
        "to_chunk_id": to_id,
        "label": label,
        "weight": weight,
        "project_id": project_id,
    }
    try:
        relation = request("POST", "/chunks/relations", payload)
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            return None
        raise
    existing.append(relation)
    return relation


def main() -> None:
    project_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROJECT_ID
    encoded_project = urllib.parse.quote(project_id, safe="")
    manual_chunks = get_json(f"/chunks/manual?project_id={encoded_project}")
    existing_nodes = {chunk.get("label"): chunk for chunk in manual_chunks if chunk.get("label")}
    node_by_label = {
        spec["label"]: ensure_node(project_id, spec, existing_nodes)
        for spec in NODES
    }

    relations = get_json(f"/chunks/relations?project_id={encoded_project}")
    created_or_existing = []
    for from_label, to_label, label, weight in RELATIONS:
        relation = ensure_relation(
            project_id,
            node_by_label[from_label]["chunk_id"],
            node_by_label[to_label]["chunk_id"],
            label,
            weight,
            relations,
        )
        created_or_existing.append(relation)

    print(json.dumps({
        "project_id": project_id,
        "source_doc": SOURCE_DOC,
        "nodes_total": len(node_by_label),
        "relations_total": len([r for r in created_or_existing if r]),
        "node_labels": list(node_by_label.keys()),
        "relations": [
            {
                "from": from_label,
                "to": to_label,
                "label": label,
                "weight": weight,
            }
            for from_label, to_label, label, weight in RELATIONS
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
