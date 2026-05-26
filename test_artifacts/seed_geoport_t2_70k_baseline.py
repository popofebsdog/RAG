from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request


BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PROJECT_ID = "proj_1778639365155"
SOURCE_DOC = "GeoPORT 台2線70.1K 崩塌初勘報告 2024-06-20"
SOURCE_URL = "https://jatestrella.github.io/GeoPORT/20240603_T2_70p1k_update/index.html"


NODES = [
    {
        "label": "台2線70.1K平浪橋南側邊坡",
        "text": "GeoPORT 初勘報告指出，本案發生地點為台2線70.1K，平浪橋南側邊坡，座標約為 25°08'23.3\"N, 121°48'06.1\"E。此節點作為事件空間基準。",
        "perspective": "geoport_location",
    },
    {
        "label": "八斗子雨量站前三日累積雨量57.5mm",
        "text": "初勘投影片記錄前期降雨：八斗子雨量站前三日累積雨量為 57.5 mm。此數值可作為本事件降雨條件的穩定基準。",
        "perspective": "geoport_rainfall",
    },
    {
        "label": "6/2 09至6/3 04集中降雨46mm",
        "text": "初勘投影片記錄雨量集中於 6/2 09:00 至 6/3 04:00，累積約 46 mm。此節點描述災害前短延時集中降雨。",
        "perspective": "geoport_rainfall",
    },
    {
        "label": "歷史災害紀錄20160203_20161012_20230428",
        "text": "投影片列出歷史災害紀錄：20160203、20161012、20230428，表示台2線70.1K附近邊坡具重複災害背景。",
        "perspective": "geoport_history",
    },
    {
        "label": "E層高度風化岩體局部崩落",
        "text": "破壞機制分析指出：崩塌初期，西側 E 層之高度風化岩體發生局部崩落，是後續破壞鏈的起始事件。",
        "perspective": "geoport_mechanism",
    },
    {
        "label": "F層厚層砂岩受到擾動",
        "text": "E層高度風化岩體局部崩落後，上方 F 層厚層砂岩受到擾動，造成後續裂縫與岩體分離。",
        "perspective": "geoport_mechanism",
    },
    {
        "label": "後方張裂縫張開",
        "text": "破壞機制指出，F層受擾動後，後方張裂縫張開，表示岩體已與坡體產生拉張分離。",
        "perspective": "geoport_mechanism",
    },
    {
        "label": "F層厚層砂岩與冠部及兩側脫離",
        "text": "F層厚層砂岩與冠部及兩側脫離，使其重量重新分配至下方 E 層與 D 層風化岩體。",
        "perspective": "geoport_mechanism",
    },
    {
        "label": "F層厚層砂岩自重施加於E層與D層風化岩體",
        "text": "F層厚層砂岩脫離後，是該厚層砂岩自身重量施加於 E 層與 D 層之風化岩體，造成下方岩體受力增加；此處不是車輛重量或交通載重。",
        "perspective": "geoport_mechanism",
    },
    {
        "label": "岩橋斷裂與貫通節理",
        "text": "下方 E 層與 D 層風化岩體受力後，內部發生岩橋斷裂與貫通節理，弱面逐漸連續化。",
        "perspective": "geoport_mechanism",
    },
    {
        "label": "E層與D層內形成破壞面",
        "text": "岩橋斷裂與節理貫通後，E層與D層內部形成破壞面，提供 F 層厚層砂岩下滑路徑。",
        "perspective": "geoport_mechanism",
    },
    {
        "label": "F層厚層砂岩沿破壞面下滑",
        "text": "破碎材料不斷崩落後，F層厚層砂岩沿 E 層與 D 層內之破壞面下滑，初期呈現向後傾移動。",
        "perspective": "geoport_mechanism",
    },
    {
        "label": "階梯狀破壞面造成重心失穩",
        "text": "投影片指出，F層厚層砂岩受底下階梯狀破壞面影響，很快發生重心失穩。",
        "perspective": "geoport_mechanism",
    },
    {
        "label": "厚層砂岩轉為傾覆崩落至路面",
        "text": "重心失穩後，厚層砂岩轉向以傾覆為主要運動行為，最後崩落至台2線路面。",
        "perspective": "geoport_outcome",
    },
    {
        "label": "台2線路面受崩落影響",
        "text": "F層厚層砂岩與破碎材料崩落至路面，使台2線道路受到災害影響。",
        "perspective": "geoport_impact",
    },
]


RELATIONS = [
    ("台2線70.1K平浪橋南側邊坡", "八斗子雨量站前三日累積雨量57.5mm", "具有前期降雨", 0.72),
    ("台2線70.1K平浪橋南側邊坡", "6/2 09至6/3 04集中降雨46mm", "具有集中降雨", 0.76),
    ("台2線70.1K平浪橋南側邊坡", "歷史災害紀錄20160203_20161012_20230428", "具有歷史災害", 0.82),
    ("E層高度風化岩體局部崩落", "F層厚層砂岩受到擾動", "導致", 0.95),
    ("F層厚層砂岩受到擾動", "後方張裂縫張開", "導致", 0.93),
    ("後方張裂縫張開", "F層厚層砂岩與冠部及兩側脫離", "促成", 0.88),
    ("F層厚層砂岩與冠部及兩側脫離", "F層厚層砂岩自重施加於E層與D層風化岩體", "導致", 0.93),
    ("F層厚層砂岩自重施加於E層與D層風化岩體", "岩橋斷裂與貫通節理", "導致", 0.95),
    ("岩橋斷裂與貫通節理", "E層與D層內形成破壞面", "導致", 0.96),
    ("E層與D層內形成破壞面", "F層厚層砂岩沿破壞面下滑", "提供下滑面", 0.94),
    ("F層厚層砂岩沿破壞面下滑", "階梯狀破壞面造成重心失穩", "導致", 0.88),
    ("階梯狀破壞面造成重心失穩", "厚層砂岩轉為傾覆崩落至路面", "導致", 0.96),
    ("厚層砂岩轉為傾覆崩落至路面", "台2線路面受崩落影響", "造成", 0.95),
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
    node = request("POST", "/chunks/manual", {
        "label": spec["label"],
        "text": f"{spec['text']} 來源：{SOURCE_URL}",
        "source_doc": SOURCE_DOC,
        "project_id": project_id,
        "region": "台2線70.1K",
        "year": 2024,
        "perspective": spec["perspective"],
    })
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
    try:
        relation = request("POST", "/chunks/relations", {
            "from_chunk_id": from_id,
            "to_chunk_id": to_id,
            "label": label,
            "weight": weight,
            "project_id": project_id,
        })
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
    node_by_label = {spec["label"]: ensure_node(project_id, spec, existing_nodes) for spec in NODES}
    relations = get_json(f"/chunks/relations?project_id={encoded_project}")
    kept_relations = []
    for from_label, to_label, label, weight in RELATIONS:
        relation = ensure_relation(
            project_id,
            node_by_label[from_label]["chunk_id"],
            node_by_label[to_label]["chunk_id"],
            label,
            weight,
            relations,
        )
        kept_relations.append(relation)
    print(json.dumps({
        "project_id": project_id,
        "source_doc": SOURCE_DOC,
        "source_url": SOURCE_URL,
        "nodes_total": len(node_by_label),
        "relations_total": len([rel for rel in kept_relations if rel]),
        "node_labels": list(node_by_label.keys()),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
