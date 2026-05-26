from __future__ import annotations

import os
import re
from dataclasses import dataclass

import numpy as np

from .loader import PageContent


@dataclass
class Chunk:
    chunk_id: str
    text: str
    source_page: int
    start_char: int
    end_char: int
    source_doc: str = ""
    source_anchor: str | None = None


def _split_sentences(text: str) -> list[tuple[str, int, int]]:
    """Return list of (stripped_sentence, raw_start, raw_end) triples.
    raw_start/raw_end are byte positions in the original text (before strip).
    When short segments are merged, raw_start/raw_end span the full range so
    that page.text[raw_start:raw_end] is always a valid substring of the original.
    """
    split_points = [0]
    for m in re.finditer(r'[。！？.!?]\s*', text):
        split_points.append(m.end())
    split_points.append(len(text))

    raw: list[tuple[str, int, int]] = []
    for i in range(len(split_points) - 1):
        rs, re_ = split_points[i], split_points[i + 1]
        seg = text[rs:re_].strip()
        if seg:
            raw.append((seg, rs, re_))

    # Merge short segments: extend raw_end so the slice stays valid
    result: list[tuple[str, int, int]] = []
    buf = ""
    buf_rs = buf_re = 0
    for seg, rs, re_ in raw:
        if not buf:
            buf, buf_rs, buf_re = seg, rs, re_
        else:
            buf += seg          # for length check only; not used as chunk text
            buf_re = re_
        if len(buf) >= 30:
            result.append((buf, buf_rs, buf_re))
            buf = ""
    if buf:
        result.append((buf, buf_rs, buf_re))
    return result


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0


def _make_id(page: int, text: str) -> str:
    snippet = re.sub(r'\s+', ' ', text.strip())[:32].rstrip()
    slug = re.sub(r'[^\w\s-]', '', snippet).strip().replace(' ', '-').lower()
    return f"p{page}:{slug}"


def semantic_chunk(
    pages: list[PageContent],
    breakpoint_threshold: float | None = None,
    max_chunk_size: int = 1200,
) -> list[Chunk]:
    from .embedding import embed_texts

    # nomic-embed-text scores are higher overall; use 0.70 as breakpoint
    threshold = breakpoint_threshold or float(os.getenv("SEMANTIC_THRESHOLD", "0.70"))
    chunks: list[Chunk] = []

    for page in pages:
        sentences_with_pos = _split_sentences(page.text)
        if not sentences_with_pos:
            continue

        # texts: stripped sentence strings, used only for embedding similarity
        # raw_starts / raw_ends: positions in original page.text
        texts     = [s   for s, _, _  in sentences_with_pos]
        raw_starts = [rs  for _, rs, _ in sentences_with_pos]
        raw_ends   = [re_ for _, _, re_ in sentences_with_pos]

        def emit_chunk(indices: list[int]) -> None:
            cs = raw_starts[indices[0]]
            ce = raw_ends[indices[-1]]
            ct = page.text[cs:ce]
            chunks.append(Chunk(
                chunk_id=_make_id(page.page_num, ct),
                text=ct,
                source_page=page.page_num,
                start_char=cs,
                end_char=ce,
            ))

        if len(texts) == 1:
            emit_chunk([0])
            continue

        embeddings = embed_texts(texts)
        sims = [_cosine_sim(embeddings[i], embeddings[i + 1]) for i in range(len(embeddings) - 1)]

        current_indices: list[int] = [0]

        for i, sim in enumerate(sims):
            next_idx = i + 1
            # combined span in original text if we include next sentence
            combined_len = raw_ends[next_idx] - raw_starts[current_indices[0]]
            if sim < threshold or combined_len > max_chunk_size:
                emit_chunk(current_indices)
                current_indices = [next_idx]
            else:
                current_indices.append(next_idx)

        if current_indices:
            emit_chunk(current_indices)

    return chunks


def chunk_pages(
    pages: list[PageContent],
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    mode = os.getenv("CHUNK_MODE", "semantic").lower()
    if mode == "semantic":
        try:
            return semantic_chunk(pages)
        except Exception:
            pass

    chunk_size = chunk_size or int(os.getenv("CHUNK_SIZE", 500))
    overlap = overlap or int(os.getenv("CHUNK_OVERLAP", 50))
    chunks: list[Chunk] = []
    for page in pages:
        text = page.text
        start = 0
        idx = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(Chunk(
                    chunk_id=_make_id(page.page_num, chunk_text),
                    text=chunk_text,
                    source_page=page.page_num,
                    start_char=start,
                    end_char=end,
                ))
                idx += 1
            start = end - overlap if end < len(text) else len(text)
    return chunks
