from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class PageContent:
    page_num: int
    text: str


@dataclass
class PageImage:
    page_num: int
    image_index: int   # 0-based index within the page
    data_b64: str      # PNG base64
    width: int
    height: int


class PDFLoader(Protocol):
    def load(self, path: str) -> list[PageContent]: ...


class PyMuPDFLoader:
    """Text-layer extraction. Falls back to Tesseract OCR for scanned pages."""

    def load_images(self, path: str, min_size: int = 100) -> list[PageImage]:
        """Extract images from every page. Skips images smaller than min_size px."""
        import fitz

        doc = fitz.open(path)
        images: list[PageImage] = []
        for page in doc:
            page_num = page.number + 1
            for img_index, img_info in enumerate(page.get_images(full=True)):
                xref = img_info[0]
                try:
                    base_img = doc.extract_image(xref)
                    w, h = base_img["width"], base_img["height"]
                    if w < min_size or h < min_size:
                        continue
                    import fitz as _fitz
                    pix = _fitz.Pixmap(doc, xref)
                    if pix.n > 4:            # CMYK → RGB
                        pix = _fitz.Pixmap(_fitz.csRGB, pix)
                    png_bytes = pix.tobytes("png")
                    images.append(PageImage(
                        page_num=page_num,
                        image_index=img_index,
                        data_b64=base64.b64encode(png_bytes).decode(),
                        width=pix.width,
                        height=pix.height,
                    ))
                except Exception:
                    continue
        doc.close()
        return images

    def load(self, path: str) -> list[PageContent]:
        import fitz

        doc = fitz.open(path)
        pages: list[PageContent] = []
        scanned_pages: list[tuple[int, object]] = []

        for i, page in enumerate(doc):
            text = page.get_text().strip()
            if text:
                pages.append(PageContent(page_num=i + 1, text=text))
            else:
                scanned_pages.append((i + 1, page))

        if scanned_pages:
            ocr_pages = _ocr_pages(doc, scanned_pages)
            pages.extend(ocr_pages)
            pages.sort(key=lambda p: p.page_num)

        doc.close()
        return pages


class PyMuPDF4LLMLoader:
    """RAG-oriented PDF-to-Markdown parser.

    Chosen as the default because it preserves reading order and tables as
    Markdown while staying lightweight enough for a one-week local demo.
    """

    def load(self, path: str) -> list[PageContent]:
        try:
            import pymupdf4llm
        except ImportError as exc:
            raise RuntimeError("pymupdf4llm not installed. Run: pip install pymupdf4llm") from exc

        try:
            chunks = pymupdf4llm.to_markdown(path, page_chunks=True)
        except TypeError:
            chunks = None

        if isinstance(chunks, list):
            pages: list[PageContent] = []
            for i, item in enumerate(chunks, start=1):
                text = (item.get("text") or item.get("markdown") or "").strip()
                metadata = item.get("metadata") or {}
                page_num = int(metadata.get("page") or metadata.get("page_number") or i)
                if text:
                    pages.append(PageContent(page_num=page_num, text=text))
            if pages:
                return pages

        markdown = pymupdf4llm.to_markdown(path)
        if isinstance(markdown, str) and markdown.strip():
            return [PageContent(page_num=1, text=markdown.strip())]
        return PyMuPDFLoader().load(path)


class VLMPDFLoader:
    """Vision-language parser for image-heavy PDFs and slide decks.

    It renders each page to an image, asks a VLM to extract structured disaster
    investigation facts, and returns one Markdown-like text block per page.
    """

    def load(self, path: str) -> list[PageContent]:
        rendered = _render_pdf_pages(path)
        if not rendered:
            return []

        concurrency = max(1, int(os.getenv("VLM_CONCURRENCY", "4")))
        pages_by_num: dict[int, PageContent] = {}

        def extract(item: tuple[int, list[str]]) -> tuple[int, str]:
            page_num, image_b64s = item
            print(f"[VLM] extracting page {page_num}/{len(rendered)} images={len(image_b64s)}", flush=True)
            started = time.time()
            text, cache_hit = _vlm_extract_page_cached(image_b64s, page_num)
            print(
                f"[VLM] finished page {page_num}/{len(rendered)} "
                f"chars={len(text.strip())} source={'cache' if cache_hit else 'api'} "
                f"elapsed={time.time() - started:.1f}s",
                flush=True,
            )
            return page_num, text

        if concurrency == 1 or len(rendered) == 1:
            results = [extract(item) for item in rendered]
        else:
            workers = min(concurrency, len(rendered))
            print(f"[VLM] parallel extraction workers={workers}", flush=True)
            results: list[tuple[int, str]] = []
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {executor.submit(extract, item): item[0] for item in rendered}
                for future in as_completed(future_map):
                    results.append(future.result())

        for page_num, text in results:
            if text.strip():
                pages_by_num[page_num] = PageContent(page_num=page_num, text=text.strip())
        return [pages_by_num[p] for p in sorted(pages_by_num)]


def _ocr_pages(doc: object, scanned: list[tuple[int, object]]) -> list[PageContent]:
    try:
        import pytesseract
        from PIL import Image
        import io
    except ImportError:
        return []

    results: list[PageContent] = []
    for page_num, page in scanned:
        try:
            mat = page.get_pixmap(dpi=200)  # type: ignore[attr-defined]
            img = Image.open(io.BytesIO(mat.tobytes("png")))
            text = pytesseract.image_to_string(img).strip()
            if text:
                results.append(PageContent(page_num=page_num, text=text))
        except Exception:
            continue
    return results


def _render_pdf_pages(path: str) -> list[tuple[int, list[str]]]:
    import fitz

    dpi = int(os.getenv("VLM_RENDER_DPI", "160"))
    max_pages = int(os.getenv("VLM_MAX_PAGES", "20"))
    use_tiles = os.getenv("VLM_PAGE_TILES", "1") != "0"
    tile_grid = max(1, int(os.getenv("VLM_TILE_GRID", "2")))
    doc = fitz.open(path)
    rendered: list[tuple[int, list[str]]] = []
    try:
        for index in range(min(len(doc), max_pages)):
            page = doc[index]
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            png = pix.tobytes("png")
            page_images = [base64.b64encode(png).decode("ascii")]

            if use_tiles and tile_grid > 1:
                rect = page.rect
                tile_width = rect.width / tile_grid
                tile_height = rect.height / tile_grid
                for row in range(tile_grid):
                    for col in range(tile_grid):
                        clip = fitz.Rect(
                            rect.x0 + col * tile_width,
                            rect.y0 + row * tile_height,
                            rect.x0 + (col + 1) * tile_width,
                            rect.y0 + (row + 1) * tile_height,
                        )
                        tile_pix = page.get_pixmap(dpi=dpi, alpha=False, clip=clip)
                        page_images.append(base64.b64encode(tile_pix.tobytes("png")).decode("ascii"))

            rendered.append((page.number + 1, page_images))
    finally:
        doc.close()
    return rendered


_VLM_PROMPT_VERSION = "2026-05-27-disaster-kg-v4-review-nodes"


def _vlm_cache_dir() -> str:
    path = os.getenv(
        "VLM_CACHE_DIR",
        os.path.join(os.path.dirname(__file__), "..", "vlm_cache"),
    )
    os.makedirs(path, exist_ok=True)
    return path


def _vlm_cache_key(image_b64s: list[str], page_num: int) -> str:
    provider = os.getenv("VLM_PROVIDER", os.getenv("LLM_PROVIDER", "anthropic")).lower()
    model = (
        os.getenv("ANTHROPIC_VISION_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"))
        if provider == "anthropic"
        else os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini")
    )
    fingerprint = "|".join([
        _VLM_PROMPT_VERSION,
        provider,
        model,
        str(os.getenv("VLM_RENDER_DPI", "160")),
        str(page_num),
        hashlib.sha256("".join(hashlib.sha256(img.encode("ascii")).hexdigest() for img in image_b64s).encode("ascii")).hexdigest(),
    ])
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


def _vlm_cache_path(cache_key: str) -> str:
    return os.path.join(_vlm_cache_dir(), f"{cache_key}.json")


def _vlm_extract_page_cached(image_b64s: list[str], page_num: int) -> tuple[str, bool]:
    use_cache = os.getenv("VLM_CACHE", "1") != "0"
    cache_key = _vlm_cache_key(image_b64s, page_num)
    cache_path = _vlm_cache_path(cache_key)
    if use_cache and os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)
            return str(data.get("text") or ""), True
        except Exception:
            pass

    text = _vlm_extract_page(image_b64s, page_num)
    if use_cache:
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "page_num": page_num,
                        "prompt_version": _VLM_PROMPT_VERSION,
                        "provider": os.getenv("VLM_PROVIDER", os.getenv("LLM_PROVIDER", "anthropic")).lower(),
                        "model": os.getenv("OPENAI_VISION_MODEL") or os.getenv("ANTHROPIC_VISION_MODEL") or "",
                        "created_at": int(time.time()),
                        "text": text,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception:
            pass
    return text, False


def _vlm_extract_page(image_b64s: list[str], page_num: int) -> str:
    provider = os.getenv("VLM_PROVIDER", os.getenv("LLM_PROVIDER", "anthropic")).lower()
    if provider == "anthropic":
        return _anthropic_vision_extract(image_b64s, page_num)
    if provider == "openai":
        return _openai_vision_extract(image_b64s, page_num)
    raise RuntimeError("VLM loader supports VLM_PROVIDER=anthropic or VLM_PROVIDER=openai")


def _anthropic_vision_extract(image_b64s: list[str], page_num: int) -> str:
    import anthropic

    model = os.getenv("ANTHROPIC_VISION_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"))
    client = anthropic.Anthropic()
    prompt = f"""你正在讀取一頁災害調查投影片影像。請不要做一般 OCR 逐字轉錄，而是抽取可用於 RAG 與知識圖譜的乾淨資訊。

請只根據影像可見內容輸出繁體中文 Markdown，格式固定如下：

## Page {page_num}
### 頁面摘要
- ...
### 關鍵事實
- ...
### 圖像證據
- image: 整頁/左上/右上/左下/右下 | observation: ... | implication: ...
### 建議節點
- label: ... | evidence: ...
### 建議關係
- from: ... | relation: 導致/促成/形成/提供條件/影響/位於/具有條件/觀測到 | to: ... | evidence: ...
### 數值與位置
- ...
### 不確定或低信心
- ...

規則：
- 第一張圖是整頁，後續圖片是同頁放大切片，請交叉比對，不要把切片視為不同頁。
- 必須主動閱讀照片、地形圖、剖面圖、立體圖、標註箭頭、圖例與尺寸線；不要只讀標題和文字框。
- 圖像證據至少列出 2 條；若頁面沒有圖表/照片，才可寫「無」。
- 修正常見 OCR 誤判，例如「月塌」應理解為「崩塌」、「張列縫」應理解為「張裂縫」。
- 保留地名、里程、日期、雨量、座標、地層名稱、破壞機制。
- 若圖上只有圖形沒有可靠文字，請說明可見的地質/破壞語意，不要編造數值。
- relation 必須有方向，且 from/to 必須像可放在圖上的短節點名稱。
- 優先抽取災害事件、雨量、地質、岩體、裂縫、破壞面、崩落/傾覆機制與災損影響。
- 如果頁面主要是團隊成員、致謝、聲明或參考連結，只做摘要與關鍵事實，不要輸出「建議節點」與「建議關係」。
"""
    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": image_b64,
            },
        }
        for image_b64 in image_b64s
    ]
    content.append({"type": "text", "text": prompt})

    try:
        message = client.messages.create(
            model=model,
            max_tokens=int(os.getenv("VLM_MAX_TOKENS", "1400")),
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
        )
    except Exception as exc:
        raise RuntimeError(_summarize_vlm_error(exc, "Anthropic VLM")) from exc
    text = "\n".join(
        block.text for block in message.content
        if getattr(block, "type", "") == "text" and getattr(block, "text", "")
    )
    return _clean_vlm_text(text)


def _openai_vision_extract(image_b64s: list[str], page_num: int) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required when VLM_PROVIDER=openai")

    import httpx

    model = os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini")
    prompt = f"""你正在讀取一頁災害調查投影片影像。請不要逐字 OCR，而是抽取可用於 RAG 與知識圖譜的乾淨資訊。

輸出繁體中文 Markdown，格式固定：
## Page {page_num}
### 頁面摘要
- ...
### 關鍵事實
- ...
### 圖像證據
- image: 整頁/左上/右上/左下/右下 | observation: ... | implication: ...
### 建議節點
- label: ... | evidence: ...
### 建議關係
- from: ... | relation: 導致/促成/形成/提供條件/影響/位於/具有條件/觀測到 | to: ... | evidence: ...
### 數值與位置
- ...
### 不確定或低信心
- ...

請修正常見 OCR 誤判，例如「月塌」理解為「崩塌」、「張列縫」理解為「張裂縫」、「買通節理」理解為「貫通節理」。
第一張圖是整頁，後續圖片是同頁放大切片，請交叉比對，不要把切片視為不同頁。
必須主動閱讀照片、地形圖、剖面圖、立體圖、標註箭頭、圖例與尺寸線；不要只讀標題和文字框。
圖像證據至少列出 2 條；若頁面沒有圖表/照片，才可寫「無」。
優先抽取災害事件、雨量、地質、岩體、裂縫、破壞面、崩落/傾覆機制與災損影響。
如果頁面主要是團隊成員、致謝、聲明或參考連結，只做摘要與關鍵事實，不要輸出「建議節點」與「建議關係」。
"""
    content = [{"type": "input_text", "text": prompt}]
    content.extend(
        {"type": "input_image", "image_url": f"data:image/png;base64,{image_b64}"}
        for image_b64 in image_b64s
    )
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": content,
            }
        ],
        "max_output_tokens": int(os.getenv("VLM_MAX_TOKENS", "1400")),
    }
    try:
        resp = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=float(os.getenv("VLM_TIMEOUT", "120")),
        )
        resp.raise_for_status()
    except Exception as exc:
        raise RuntimeError(_summarize_vlm_error(exc, "OpenAI VLM")) from exc

    data = resp.json()
    text = data.get("output_text")
    if not text:
        parts: list[str] = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    parts.append(content["text"])
        text = "\n".join(parts)
    return _clean_vlm_text(text or "")


def _summarize_vlm_error(exc: Exception, provider_name: str) -> str:
    text = str(exc)
    if "credit balance" in text.lower() or "billing" in text.lower():
        return f"{provider_name} 無法使用：帳戶額度或 billing 不足。請補充額度，或改設 VLM_PROVIDER=openai 並提供 OPENAI_API_KEY。"
    if "api_key" in text.lower() or "authentication" in text.lower() or "unauthorized" in text.lower():
        return f"{provider_name} 無法使用：API key 未設定或驗證失敗。"
    return f"{provider_name} 解析失敗：{text[:240]}"


def _clean_vlm_text(text: str) -> str:
    value = re.sub(r"\n{3,}", "\n\n", text or "").strip()
    value = value.replace("月塌", "崩塌").replace("張列縫", "張裂縫").replace("買通節理", "貫通節理")
    value = value.replace("下濃", "下滑")
    return value


class ChandraLoader:
    """OCR loader for scanned PDFs. Requires chandra-ocr + vLLM server."""

    def load(self, path: str) -> list[PageContent]:
        try:
            from chandra import run_ocr
        except ImportError as e:
            raise RuntimeError("chandra-ocr not installed. Run: pip install chandra-ocr") from e

        result = run_ocr(path, method="local")
        pages: list[PageContent] = []
        for i, page_md in enumerate(result.get("pages", [])):
            text = page_md.get("markdown", "")
            if text.strip():
                pages.append(PageContent(page_num=i + 1, text=text))
        return pages


class DoclingLoader:
    """IBM Docling — handles double-column, tables, figure captions.
    Falls back to PyMuPDF if docling is not installed."""

    def load(self, path: str) -> list[PageContent]:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise RuntimeError(
                "docling not installed. Run: pip install docling"
            ) from exc

        converter = DocumentConverter()
        result = converter.convert(path)
        doc = result.document

        page_texts: dict[int, list[str]] = {}

        for item, _ in doc.iterate_items():
            # Resolve page number from provenance
            page_no = 1
            if hasattr(item, "prov") and item.prov:
                prov = item.prov[0]
                page_no = getattr(prov, "page_no", 1)

            # Extract text — plain text or markdown (tables)
            text: str | None = None
            if hasattr(item, "export_to_markdown"):
                try:
                    text = item.export_to_markdown()
                except Exception:
                    pass
            if not text and hasattr(item, "text"):
                text = item.text

            if text and text.strip():
                page_texts.setdefault(page_no, []).append(text.strip())

        pages: list[PageContent] = []
        for page_no in sorted(page_texts.keys()):
            combined = "\n\n".join(page_texts[page_no])
            if combined.strip():
                pages.append(PageContent(page_num=page_no, text=combined))

        return pages


def get_loader() -> PDFLoader:
    loader_type = os.getenv("PDF_LOADER", "pymupdf4llm").lower()
    if loader_type in {"vlm", "vision", "multimodal"}:
        return VLMPDFLoader()
    if loader_type in {"pymupdf4llm", "auto", "best"}:
        return PyMuPDF4LLMLoader()
    if loader_type == "docling":
        return DoclingLoader()
    if loader_type in {"chandra", "ocr"}:
        return ChandraLoader()
    return PyMuPDFLoader()
