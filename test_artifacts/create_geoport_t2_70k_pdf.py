from __future__ import annotations

from pathlib import Path
import textwrap

import fitz


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "geoport_t2_70k"
OUTPUT = ROOT / "geoport_t2_70k_from_ocr.pdf"
FONT = Path("/Library/Fonts/Arial Unicode.ttf")
if not FONT.exists():
    FONT = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")


def draw_wrapped(page: fitz.Page, text: str, x: float, y: float, width: int = 46) -> float:
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            y += 7
            continue
        for wrapped in textwrap.wrap(line, width=width, break_long_words=False):
            page.insert_text((x, y), wrapped, fontsize=9.5, fontname="ArialUnicode", color=(0.12, 0.14, 0.18))
            y += 13
    return y


def build_pdf() -> None:
    doc = fitz.open()
    for page_no in range(1, 15):
        txt_path = SOURCE / f"p{page_no}.txt"
        if not txt_path.exists():
            continue
        text = txt_path.read_text(encoding="utf-8")
        page = doc.new_page(width=595, height=842)
        page.insert_font(fontname="ArialUnicode", fontfile=str(FONT))
        page.insert_text(
            (42, 48),
            f"GeoPORT 台2線70.1K 初勘報告 OCR p.{page_no}",
            fontsize=15,
            fontname="ArialUnicode",
            color=(0.05, 0.14, 0.26),
        )
        draw_wrapped(page, text, 42, 82)
        page.insert_text((520, 812), f"p.{page_no}", fontsize=9, fontname="ArialUnicode", color=(0.40, 0.44, 0.50))
    doc.set_metadata(
        {
            "title": "GeoPORT 台2線70.1K 初勘報告 OCR 測試 PDF",
            "author": "Codex",
            "subject": "Converted from local GeoPORT OCR text for Visual RAG workflow evaluation",
        }
    )
    doc.save(OUTPUT)
    doc.close()
    print(OUTPUT)


if __name__ == "__main__":
    build_pdf()
