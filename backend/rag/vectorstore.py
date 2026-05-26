from __future__ import annotations

from dataclasses import dataclass, field

import faiss
import numpy as np

from .chunking import Chunk


@dataclass
class VectorStore:
    chunks: list[Chunk] = field(default_factory=list)
    embeddings: np.ndarray = field(default_factory=lambda: np.empty((0, 0)))
    _index: faiss.IndexFlatIP | None = field(default=None, repr=False)

    def build(self, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        """Replace entire index."""
        self.chunks = list(chunks)
        self.embeddings = embeddings
        dim = embeddings.shape[1]
        self._index = faiss.IndexFlatIP(dim)
        self._index.add(embeddings.astype("float32"))

    def append(self, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        """Add to existing index without replacing."""
        if not self.is_ready:
            self.build(chunks, embeddings)
            return
        self.chunks.extend(chunks)
        self.embeddings = np.vstack([self.embeddings, embeddings])
        self._index.add(embeddings.astype("float32"))  # type: ignore[union-attr]

    def remove_doc(self, source_doc: str) -> None:
        """Remove all chunks belonging to a document and rebuild index."""
        keep = [c for c in self.chunks if c.source_doc != source_doc]
        if not keep:
            self.clear()
            return
        keep_idx = [i for i, c in enumerate(self.chunks) if c.source_doc != source_doc]
        new_emb = self.embeddings[keep_idx]
        self.build(keep, new_emb)

    def clear(self) -> None:
        self.chunks = []
        self.embeddings = np.empty((0, 0))
        self._index = None

    def search(self, query_vec: np.ndarray, top_k: int = 5) -> list[tuple[Chunk, float]]:
        if self._index is None or self._index.ntotal == 0:
            return []
        scores, indices = self._index.search(
            query_vec.reshape(1, -1).astype("float32"), top_k
        )
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1:
                results.append((self.chunks[idx], float(score)))
        return results

    @property
    def is_ready(self) -> bool:
        return self._index is not None and self._index.ntotal > 0

    @property
    def chunk_count(self) -> int:
        return self._index.ntotal if self._index else 0

    def docs(self) -> list[str]:
        seen: list[str] = []
        for c in self.chunks:
            if c.source_doc not in seen:
                seen.append(c.source_doc)
        return seen


_store: VectorStore = VectorStore()


def get_store() -> VectorStore:
    return _store
