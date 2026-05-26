from __future__ import annotations

import os

import httpx
import numpy as np

from .chunking import Chunk

OLLAMA_URL   = os.getenv("OLLAMA_URL",   "http://localhost:11434")
EMBED_MODEL  = os.getenv("EMBED_MODEL",  "nomic-embed-text")
EMBED_DIM    = 768  # nomic-embed-text output dimension


def _embed(texts: list[str]) -> np.ndarray:
    """Call Ollama /api/embed and return L2-normalised float32 array."""
    resp = httpx.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": texts},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    # Ollama returns {"embeddings": [[...], ...]}
    vecs = np.array(data["embeddings"], dtype="float32")
    # L2 normalise so cosine similarity = dot product
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return vecs / norms


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a list of raw strings. Used by semantic chunking."""
    return _embed(texts)


def embed_chunks(chunks: list[Chunk]) -> np.ndarray:
    texts = [c.text for c in chunks]
    return _embed(texts)


def embed_query(query: str) -> np.ndarray:
    return _embed([query])[0]
