from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from .loader import PageContent


_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "markdown_cache")


@dataclass
class AnchorRecord:
    anchor: str
    page_num: int
    title: str
    text: str


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w\-.]", "_", name)


def _project_dir(project_id: str) -> str:
    path = os.path.join(_BASE_DIR, _safe_name(project_id))
    os.makedirs(path, exist_ok=True)
    return path


def _markdown_path(source_doc: str, project_id: str) -> str:
    return os.path.join(_project_dir(project_id), f"{_safe_name(source_doc)}.md")


def _anchors_path(source_doc: str, project_id: str) -> str:
    return os.path.join(_project_dir(project_id), f"{_safe_name(source_doc)}.anchors.json")


def _slug(text: str) -> str:
    value = re.sub(r"\s+", "-", text.strip().lower())
    value = re.sub(r"[^\w\u4e00-\u9fff-]", "", value)
    return value.strip("-")[:28] or "block"


def _anchor_for(page_num: int, text: str, index: int) -> str:
    return f"^p{page_num}-{_slug(text)}-{index}"


def _split_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    for raw in re.split(r"\n\s*\n", text.strip()):
        block = raw.strip()
        if not block:
            continue
        blocks.append(block)
    return blocks


def anchor_pages(pages: list[PageContent]) -> tuple[list[PageContent], str, list[AnchorRecord]]:
    """Return pages with stable anchors appended to each meaningful block."""
    anchored_pages: list[PageContent] = []
    markdown_parts: list[str] = []
    records: list[AnchorRecord] = []

    for page in pages:
        page_blocks = _split_blocks(page.text)
        anchored_blocks: list[str] = []
        markdown_parts.append(f"# Page {page.page_num} ^p{page.page_num}\n")
        records.append(AnchorRecord(
            anchor=f"^p{page.page_num}",
            page_num=page.page_num,
            title=f"Page {page.page_num}",
            text=f"Page {page.page_num}",
        ))

        for idx, block in enumerate(page_blocks, start=1):
            title = _block_title(block)
            anchor = _anchor_for(page.page_num, title, idx)
            anchored = _append_anchor(block, anchor)
            anchored_blocks.append(anchored)
            markdown_parts.append(anchored)
            records.append(AnchorRecord(anchor=anchor, page_num=page.page_num, title=title, text=block))

        anchored_text = "\n\n".join(anchored_blocks).strip()
        anchored_pages.append(PageContent(page_num=page.page_num, text=anchored_text or page.text))
        markdown_parts.append("")

    return anchored_pages, "\n\n".join(markdown_parts).strip() + "\n", records


def _block_title(block: str) -> str:
    first = block.strip().splitlines()[0].strip()
    first = re.sub(r"^#+\s*", "", first)
    first = re.sub(r"^[-*]\s*", "", first)
    first = re.sub(r"\s+", " ", first)
    return first[:48] or "block"


def _append_anchor(block: str, anchor: str) -> str:
    lines = block.rstrip().splitlines()
    if not lines:
        return anchor
    lines[-1] = f"{lines[-1].rstrip()} {anchor}"
    return "\n".join(lines)


def store_markdown(source_doc: str, markdown: str, anchors: list[AnchorRecord], project_id: str = "default") -> None:
    with open(_markdown_path(source_doc, project_id), "w", encoding="utf-8") as f:
        f.write(markdown)
    with open(_anchors_path(source_doc, project_id), "w", encoding="utf-8") as f:
        json.dump([record.__dict__ for record in anchors], f, ensure_ascii=False, indent=2)


def get_markdown(source_doc: str, project_id: str = "default") -> str:
    path = _markdown_path(source_doc, project_id)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def get_anchors(source_doc: str, project_id: str = "default") -> list[dict]:
    path = _anchors_path(source_doc, project_id)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def remove_doc(source_doc: str, project_id: str = "default") -> None:
    for path in [_markdown_path(source_doc, project_id), _anchors_path(source_doc, project_id)]:
        if os.path.exists(path):
            os.unlink(path)


def clear(project_id: str = "default") -> None:
    directory = _project_dir(project_id)
    for name in os.listdir(directory):
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            os.unlink(path)


def first_anchor(text: str) -> str | None:
    match = re.search(r"\^p\d+[-\w\u4e00-\u9fff]*", text or "")
    return match.group(0) if match else None
