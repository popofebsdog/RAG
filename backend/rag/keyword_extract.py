from __future__ import annotations

import re
from collections import Counter


# Chinese stopwords (disaster report context)
_STOPWORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "那", "与", "对", "中", "为", "以", "及", "等", "由", "其", "此",
    "而", "被", "将", "可", "但", "并", "如", "则", "于", "该", "或", "所", "因",
    "从", "后", "前", "当", "各", "已", "均", "较", "应", "据", "作", "时", "内",
    "外", "下", "使", "当时", "进行", "通过", "结果", "可以", "同时", "情况",
    "分析", "研究", "工作", "问题", "具有", "主要", "方面", "方式", "显示",
    "表明", "认为", "指出", "发现", "影响", "相关", "相比",
}


def extract_keywords(text: str, label: str | None = None, top_n: int = 3) -> str:
    """
    Extract top keywords from text for graph node display.
    If a manual label is provided, return it directly.
    Uses jieba TF-IDF if available, falls back to frequency count.
    """
    if label:
        # Manual chunk: use user label directly, trim to reasonable length
        return label[:20]

    text = text.strip()
    if not text:
        return "…"

    try:
        import jieba.analyse  # type: ignore
        # TF-IDF keyword extraction (works well for Chinese)
        kws = jieba.analyse.extract_tags(text, topK=top_n, allowPOS=("n", "vn", "v", "an", "nz"))
        if kws:
            return " · ".join(kws[:top_n])
    except Exception:
        pass

    # Fallback: frequency-based extraction of Chinese words (2-4 chars)
    chinese_words = re.findall(r"[一-鿿]{2,4}", text)
    if chinese_words:
        words = [w for w in chinese_words if w not in _STOPWORDS]
        top = [w for w, _ in Counter(words).most_common(top_n)]
        if top:
            return " · ".join(top)

    # Last resort: first N characters
    clean = re.sub(r"\s+", " ", text[:60]).strip()
    return clean[:20] + ("…" if len(clean) > 20 else "")
