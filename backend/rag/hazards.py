from __future__ import annotations

HAZARD_KEYWORDS: dict[str, list[str]] = {
    "earthquake": ["earthquake", "seismic", "震", "地震", "斷層", "液化", "震度", "餘震", "微震"],
    "typhoon": ["typhoon", "颱風", "颱", "風災", "強風", "暴風", "環流", "外圍環流"],
    "heavy_rain": ["rainfall", "rainstorm", "heavy rain", "豪雨", "大雨", "強降雨", "集中降雨", "降雨", "雨量", "累積雨量", "前期降雨"],
    "landslide": ["landslide", "slope failure", "slope", "崩塌", "山崩", "邊坡", "滑動", "滑落", "破壞面", "張裂縫", "順向坡"],
    "rockfall": ["rockfall", "落石", "岩塊", "岩體", "砂岩", "傾覆", "岩橋", "節理", "風化岩體"],
    "debris_flow": ["debris flow", "土石流", "土砂", "泥流", "溪溝", "溝谷", "堆積", "高濃度流"],
}

LEGACY_HAZARD_ALIASES: dict[str, str] = {
    "flood": "heavy_rain",
    "tsunami": "typhoon",
    "damage": "landslide",
}


def detect_hazard_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags = [
        hazard
        for hazard, keywords in HAZARD_KEYWORDS.items()
        if any(keyword in lowered or keyword in text for keyword in keywords)
    ]
    return tags or ["general"]


def router_scores(query: str) -> dict[str, float]:
    raw: dict[str, float] = {}
    for hazard, keywords in HAZARD_KEYWORDS.items():
        raw[hazard] = 0.05 + sum(1 for keyword in keywords if keyword in query.lower() or keyword in query)
    total = sum(raw.values()) or 1.0
    return {hazard: round(score / total, 4) for hazard, score in raw.items()}
