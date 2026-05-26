from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class UMAPPoint:
    chunk_id: str
    x: float
    y: float
    text: str
    source_page: int
    is_retrieved: bool = False
    score: float = 0.0


@dataclass
class QueryPoint:
    x: float
    y: float
    label: str = "Query"


def compute_umap(
    embeddings: np.ndarray,
    query_vec: np.ndarray | None = None,
    n_neighbors: int = 15,
    min_dist: float = 0.1,
) -> tuple[np.ndarray, np.ndarray | None]:
    all_vecs = embeddings
    query_idx = None

    if query_vec is not None:
        all_vecs = np.vstack([embeddings, query_vec.reshape(1, -1)])
        query_idx = len(embeddings)

    n = len(all_vecs)

    # UMAP deadlocks with very few points (mutex issue); fall back to PCA
    if n < 6:
        from sklearn.decomposition import PCA

        n_components = min(2, n - 1) if n > 1 else 1
        pca = PCA(n_components=n_components)
        coords_2d = pca.fit_transform(all_vecs.astype("float32"))
        if coords_2d.shape[1] < 2:
            coords_2d = np.hstack([coords_2d, np.zeros((n, 1))])
    else:
        import umap

        n_neighbors = min(n_neighbors, n - 1)
        reducer = umap.UMAP(
            n_components=2,
            n_neighbors=n_neighbors,
            min_dist=min_dist,
            metric="cosine",
            random_state=42,
        )
        coords_2d = reducer.fit_transform(all_vecs.astype("float32"))

    if query_idx is not None:
        return coords_2d[:query_idx], coords_2d[query_idx]
    return coords_2d, None
