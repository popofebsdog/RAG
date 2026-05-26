from __future__ import annotations

from pathlib import Path

import fitz


SOURCE = Path("/tmp/geoport_original_images")
OUTPUT = Path(__file__).resolve().parent / "geoport_t2_70k_original_images.pdf"


def build_pdf() -> None:
    doc = fitz.open()
    for image_path in sorted(SOURCE.glob("p*.jpg"), key=lambda p: int(p.stem[1:])):
        pix = fitz.Pixmap(str(image_path))
        page = doc.new_page(width=pix.width, height=pix.height)
        page.insert_image(page.rect, filename=str(image_path))
    doc.set_metadata(
        {
            "title": "GeoPORT 台2線70.1K 原始圖片 PDF",
            "author": "Codex",
            "subject": "Built from https://jatestrella.github.io/GeoPORT/20240603_T2_70p1k/index.html",
        }
    )
    doc.save(OUTPUT)
    doc.close()
    print(OUTPUT)


if __name__ == "__main__":
    build_pdf()
