from __future__ import annotations

import re


TERM_ALIASES: dict[str, str] = {
    # disaster classes
    "山崩": "崩塌",
    "坡面崩落": "崩塌",
    "邊坡破壞": "邊坡崩塌",
    "淺層滑動": "淺層崩塌",
    "土砂流": "土石流",
    "泥流": "土石流",
    # rainfall / monitoring
    "累積降雨": "累積雨量",
    "總雨量": "累積雨量",
    "24h雨量": "24小時雨量",
    "24小時降雨": "24小時雨量",
    "前期降雨量": "前期降雨",
    "地下水位上升": "地下水位上升",
    "孔隙水壓增加": "孔隙水壓上升",
    # geology / mechanism
    "張列縫": "張裂縫",
    "拉張裂縫": "張裂縫",
    "節理貫通": "貫通節理",
    "岩橋破壞": "岩橋斷裂",
    "剪力強度降低": "剪力強度下降",
    "穩定性降低": "邊坡穩定性下降",
    "失穩": "邊坡失穩",
    "破壞滑動面": "破壞面",
}

RELATION_ALIASES: dict[str, str] = {
    "造成": "導致",
    "引起": "導致",
    "引發": "導致",
    "使得": "導致",
    "使": "導致",
    "導致": "導致",
    "觸發": "觸發",
    "促使": "促成",
    "促進": "促成",
    "促成": "促成",
    "由…促成": "促成",
    "由...促成": "促成",
    "形成": "形成",
    "發展為": "形成",
    "增加": "增加",
    "提高": "增加",
    "降低": "降低",
    "減少": "降低",
    "影響": "影響",
    "位於": "位於",
    "發生於": "發生於",
    "觀測到": "觀測到",
    "具有": "具有條件",
    "具有條件": "具有條件",
    "提供": "提供條件",
    "應用於": "應用於",
    "關聯": "關聯",
}

RELATION_WHITELIST = set(RELATION_ALIASES.values())


def normalize_text(text: str) -> str:
    value = re.sub(r"\s+", " ", text or "").strip()
    for alias, canonical in TERM_ALIASES.items():
        value = value.replace(alias, canonical)
    value = re.sub(r"(\d+(?:\.\d+)?)\s*(mm|毫米)", r"\1 mm", value, flags=re.I)
    value = re.sub(r"(\d+(?:\.\d+)?)\s*(m|公尺)", r"\1 m", value, flags=re.I)
    value = re.sub(r"(\d+(?:\.\d+)?)\s*(hr|小時)", r"\1 小時", value, flags=re.I)
    return value


def normalize_label(label: str, evidence_text: str = "") -> str:
    value = normalize_text(label)
    value = re.sub(r"^(?:[#\-\s]+|\d+[.、]\s*)+", "", value)
    value = re.sub(r"[「」\"'`]", "", value)
    value = value.strip(" ：:，,。；;")
    if _looks_like_placeholder(value):
        value = _label_from_evidence(evidence_text)
    return value[:32]


def normalize_relation_label(label: str) -> str:
    value = re.sub(r"\s+", "", str(label or "")).strip()
    value = re.sub(r"[「」\"'`]", "", value)
    return RELATION_ALIASES.get(value, value if value in RELATION_WHITELIST else "關聯")


def standardize_relation_weight(label: str, weight: float) -> float:
    canonical = normalize_relation_label(label)
    if canonical in {"導致", "觸發", "形成"}:
        return max(weight, 0.82)
    if canonical in {"促成", "增加", "降低", "提供條件"}:
        return max(weight, 0.72)
    return max(0.45, min(1.0, weight))


def _looks_like_placeholder(value: str) -> bool:
    return (
        not value
        or bool(re.fullmatch(r"node-[a-zA-Z0-9]+", value))
        or bool(re.fullmatch(r"\d+(?:\.\d+)?\s*mm", value, flags=re.I))
        or len(value) < 2
    )


def _label_from_evidence(text: str) -> str:
    value = normalize_text(text)
    for splitter in ["。", "；", "，", ":", "：", ","]:
        if splitter in value:
            value = value.split(splitter)[0]
            break
    value = re.sub(r"^[#\-\d.、\s]+", "", value).strip()
    return value[:24] or "未命名知識節點"
