from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field

import numpy as np

from .chunking import Chunk
from .hazards import detect_hazard_tags


# ── helpers ──────────────────────────────────────────────────────────────────

def _uid(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))


def _payload_to_chunk(p: dict) -> Chunk:
    return Chunk(
        chunk_id=p["chunk_id"],
        text=p["text"],
        source_page=p.get("source_page", 0),
        start_char=p.get("start_char", 0),
        end_char=p.get("end_char", 0),
        source_doc=p.get("source_doc", ""),
        source_anchor=p.get("source_anchor"),
    )


def relation_chunk_id(relation_id: str) -> str:
    return f"relation:{relation_id}"


def _extract_vector(point) -> list[float]:
    v = point.vector
    if isinstance(v, dict):
        return list(v.values())[0]
    return v or []


def _project_condition(project_id: str):
    from qdrant_client.models import FieldCondition, MatchValue
    return FieldCondition(key="project_id", match=MatchValue(value=project_id))


# ── metadata ─────────────────────────────────────────────────────────────────

@dataclass
class DocMeta:
    region: str | None = None
    year: int | None = None
    perspective: str | None = None
    project_id: str = "default"


# ── store ────────────────────────────────────────────────────────────────────

class QdrantStore:
    COLLECTION = "visual_rag"
    DIM = 768  # nomic-embed-text

    def __init__(self, url: str = "http://localhost:6333", path: str = ""):
        self._url = url
        self._path = path
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from qdrant_client import QdrantClient
            try:
                if self._path:
                    self._client = QdrantClient(path=self._path)
                else:
                    self._client = QdrantClient(url=self._url, timeout=5)
                self._ensure_collection()
            except Exception as exc:
                raise RuntimeError(
                    f"Cannot connect to Qdrant at {self._url}. "
                    "Run: docker compose up -d  (or set QDRANT_PATH=./qdrant_data for file mode)"
                ) from exc
        return self._client

    def _ensure_collection(self) -> None:
        from qdrant_client.models import Distance, VectorParams
        if self.client.collection_exists(self.COLLECTION):
            info = self.client.get_collection(self.COLLECTION)
            existing_dim = info.config.params.vectors.size
            if existing_dim != self.DIM:
                # Dimension mismatch — drop and recreate (model was switched)
                self.client.delete_collection(self.COLLECTION)
        if not self.client.collection_exists(self.COLLECTION):
            self.client.create_collection(
                collection_name=self.COLLECTION,
                vectors_config=VectorParams(size=self.DIM, distance=Distance.COSINE),
            )

    def drop_collection(self) -> None:
        """Drop and recreate the collection (clears all data across all projects)."""
        if self.client.collection_exists(self.COLLECTION):
            self.client.delete_collection(self.COLLECTION)
        self._ensure_collection()

    # ── write ────────────────────────────────────────────────────────────────

    def upsert(
        self,
        chunks: list[Chunk],
        embeddings: np.ndarray,
        meta: DocMeta | None = None,
    ) -> None:
        from qdrant_client.models import PointStruct

        meta = meta or DocMeta()
        points = [
            PointStruct(
                id=_uid(c.chunk_id),
                vector=emb.tolist(),
                payload={
                    "chunk_id": c.chunk_id,
                    "text": c.text,
                    "source_page": c.source_page,
                    "start_char": c.start_char,
                    "end_char": c.end_char,
                    "source_doc": c.source_doc,
                    "source_anchor": c.source_anchor,
                    "region": meta.region,
                    "year": meta.year,
                    "perspective": meta.perspective,
                    "project_id": meta.project_id,
                    "label": None,
                    "is_manual": False,
                    "node_type": "auto",
                    "hazard_tags": detect_hazard_tags(c.text),
                },
            )
            for c, emb in zip(chunks, embeddings)
        ]
        self.client.upsert(collection_name=self.COLLECTION, points=points)

    def upsert_manual(
        self,
        chunk: Chunk,
        embedding: np.ndarray,
        label: str,
        meta: DocMeta | None = None,
    ) -> None:
        from qdrant_client.models import PointStruct

        meta = meta or DocMeta()
        self.client.upsert(
            collection_name=self.COLLECTION,
            points=[
                PointStruct(
                    id=_uid(chunk.chunk_id),
                    vector=embedding.tolist(),
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text,
                        "source_page": chunk.source_page,
                        "start_char": 0,
                        "end_char": len(chunk.text),
                        "source_doc": chunk.source_doc,
                        "source_anchor": chunk.source_anchor,
                        "region": meta.region,
                        "year": meta.year,
                        "perspective": meta.perspective,
                        "project_id": meta.project_id,
                        "label": label,
                        "is_manual": True,
                        "node_type": "manual",
                        "hazard_tags": detect_hazard_tags(f"{label}\n{chunk.text}"),
                    },
                )
            ],
        )

    def upsert_relation(
        self,
        relation_id: str,
        embedding: np.ndarray,
        text: str,
        label: str,
        from_chunk_id: str,
        to_chunk_id: str,
        weight: float,
        project_id: str = "default",
    ) -> None:
        """Persist a manual relation as a searchable Qdrant point.

        Relations are stored as synthetic manual chunks so retrieval can surface
        user-curated causal/semantic links, not only raw text chunks.
        """
        from qdrant_client.models import PointStruct

        chunk_id = relation_chunk_id(relation_id)
        self.client.upsert(
            collection_name=self.COLLECTION,
            points=[
                PointStruct(
                    id=_uid(chunk_id),
                    vector=embedding.tolist(),
                    payload={
                        "chunk_id": chunk_id,
                        "text": text,
                        "source_page": 0,
                        "start_char": 0,
                        "end_char": len(text),
                        "source_doc": "",
                        "region": None,
                        "year": None,
                        "perspective": None,
                        "project_id": project_id,
                        "label": label,
                        "is_manual": True,
                        "node_type": "relation",
                        "relation_id": relation_id,
                        "from_chunk_id": from_chunk_id,
                        "to_chunk_id": to_chunk_id,
                        "weight": max(0.0, min(1.0, weight)),
                        "hazard_tags": detect_hazard_tags(f"{label}\n{text}"),
                    },
                )
            ],
        )

    def remove_doc(self, source_doc: str, project_id: str = "default") -> None:
        from qdrant_client.models import Filter, FieldCondition, MatchValue, FilterSelector

        self.client.delete(
            collection_name=self.COLLECTION,
            points_selector=FilterSelector(
                filter=Filter(must=[
                    FieldCondition(key="source_doc", match=MatchValue(value=source_doc)),
                    _project_condition(project_id),
                ])
            ),
        )

    def remove_chunk(self, chunk_id: str) -> None:
        self.client.delete(
            collection_name=self.COLLECTION,
            points_selector=[_uid(chunk_id)],
        )

    def remove_relation(self, relation_id: str) -> None:
        self.remove_chunk(relation_chunk_id(relation_id))

    def set_relation_weight(self, relation_id: str, weight: float) -> None:
        self.client.set_payload(
            collection_name=self.COLLECTION,
            payload={"weight": max(0.0, min(1.0, weight))},
            points=[_uid(relation_chunk_id(relation_id))],
        )

    def get_payload(self, chunk_id: str) -> dict | None:
        points = self.client.retrieve(
            collection_name=self.COLLECTION,
            ids=[_uid(chunk_id)],
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            return None
        return points[0].payload

    def clear(self, project_id: str = "default") -> None:
        """Delete all points belonging to a project."""
        from qdrant_client.models import Filter, FilterSelector

        self.client.delete(
            collection_name=self.COLLECTION,
            points_selector=FilterSelector(
                filter=Filter(must=[_project_condition(project_id)])
            ),
        )

    # ── read ─────────────────────────────────────────────────────────────────

    def search(
        self,
        query_vec: np.ndarray,
        top_k: int = 5,
        region: str | None = None,
        year: int | None = None,
        project_id: str = "default",
    ) -> list[tuple[Chunk, float]]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        conditions = [_project_condition(project_id)]
        if region:
            conditions.append(FieldCondition(key="region", match=MatchValue(value=region)))
        if year:
            conditions.append(FieldCondition(key="year", match=MatchValue(value=year)))

        response = self.client.query_points(
            collection_name=self.COLLECTION,
            query=query_vec.tolist(),
            limit=top_k,
            query_filter=Filter(must=conditions),
            with_payload=True,
        )
        results: list[tuple[Chunk, float]] = []
        for h in response.points:
            payload = h.payload
            score = h.score
            if payload.get("node_type") == "relation":
                score *= float(payload.get("weight", 1.0))
            results.append((_payload_to_chunk(payload), score))
        return results

    def search_manual(
        self,
        query_vec: np.ndarray,
        project_id: str = "default",
        limit: int = 100,
    ) -> list[tuple[Chunk, float]]:
        """Retrieve all manual chunks with their cosine similarity scores.

        Manual chunks are user-annotated supervision signals (attention anchors).
        They are always included as candidates regardless of similarity rank.
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        response = self.client.query_points(
            collection_name=self.COLLECTION,
            query=query_vec.tolist(),
            limit=limit,
            query_filter=Filter(must=[
                _project_condition(project_id),
                FieldCondition(key="is_manual", match=MatchValue(value=True)),
            ]),
            with_payload=True,
        )
        return [(_payload_to_chunk(h.payload), h.score) for h in response.points]

    def get_all(self, project_id: str = "default") -> tuple[list[Chunk], np.ndarray]:
        from qdrant_client.models import Filter

        all_points: list = []
        offset = None
        while True:
            batch, next_page = self.client.scroll(
                collection_name=self.COLLECTION,
                scroll_filter=Filter(must=[_project_condition(project_id)]),
                with_payload=True,
                with_vectors=True,
                limit=500,
                offset=offset,
            )
            all_points.extend(batch)
            if next_page is None:
                break
            offset = next_page

        chunks = [_payload_to_chunk(p.payload) for p in all_points]
        if all_points:
            embeddings = np.array([_extract_vector(p) for p in all_points], dtype="float32")
        else:
            embeddings = np.empty((0, 0))
        return chunks, embeddings

    def payloads_by_chunk_id(self, project_id: str = "default") -> dict[str, dict]:
        from qdrant_client.models import Filter

        payloads: dict[str, dict] = {}
        offset = None
        while True:
            batch, next_page = self.client.scroll(
                collection_name=self.COLLECTION,
                scroll_filter=Filter(must=[_project_condition(project_id)]),
                with_payload=True,
                with_vectors=False,
                limit=500,
                offset=offset,
            )
            for point in batch:
                payload = point.payload
                payloads[payload["chunk_id"]] = payload
            if next_page is None:
                break
            offset = next_page
        return payloads

    def docs(self, project_id: str = "default") -> list[str]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        seen: list[str] = []
        offset = None
        while True:
            batch, next_page = self.client.scroll(
                collection_name=self.COLLECTION,
                scroll_filter=Filter(must=[
                    _project_condition(project_id),
                    FieldCondition(key="is_manual", match=MatchValue(value=False)),
                ]),
                with_payload=True,
                with_vectors=False,
                limit=1000,
                offset=offset,
            )
            for p in batch:
                doc = p.payload.get("source_doc", "")
                if doc and doc not in seen:
                    seen.append(doc)
            if next_page is None:
                break
            offset = next_page
        return seen

    def manual_chunks(self, project_id: str = "default") -> list[dict]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        results, _ = self.client.scroll(
            collection_name=self.COLLECTION,
            scroll_filter=Filter(must=[
                _project_condition(project_id),
                FieldCondition(key="is_manual", match=MatchValue(value=True)),
            ]),
            with_payload=True,
            with_vectors=False,
            limit=1000,
        )
        return [p.payload for p in results if p.payload.get("node_type") != "relation"]

    def doc_chunk_count(self, source_doc: str, project_id: str = "default") -> int:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        result = self.client.count(
            collection_name=self.COLLECTION,
            count_filter=Filter(must=[
                _project_condition(project_id),
                FieldCondition(key="source_doc", match=MatchValue(value=source_doc)),
            ]),
            exact=True,
        )
        return result.count

    def chunk_count_for_project(self, project_id: str = "default") -> int:
        from qdrant_client.models import Filter
        try:
            result = self.client.count(
                collection_name=self.COLLECTION,
                count_filter=Filter(must=[_project_condition(project_id)]),
                exact=True,
            )
            return result.count
        except Exception:
            return 0

    @property
    def is_ready(self) -> bool:
        try:
            return self.client.get_collection(self.COLLECTION).points_count > 0
        except Exception:
            return False

    def is_ready_for_project(self, project_id: str) -> bool:
        return self.chunk_count_for_project(project_id) > 0

    @property
    def chunk_count(self) -> int:
        try:
            return self.client.get_collection(self.COLLECTION).points_count or 0
        except Exception:
            return 0


# ── Image collection ──────────────────────────────────────────────────────────

class ImageStore:
    """Separate Qdrant collection for CLIP image embeddings (512-dim)."""

    COLLECTION = "visual_rag_images"
    DIM = 512  # CLIP ViT-B/32

    def __init__(self, url: str = "http://localhost:6333", path: str = ""):
        self._url = url
        self._path = path
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from qdrant_client import QdrantClient
            if self._path:
                self._client = QdrantClient(path=self._path)
            else:
                self._client = QdrantClient(url=self._url, timeout=5)
            self._ensure_collection()
        return self._client

    def _ensure_collection(self) -> None:
        from qdrant_client.models import Distance, VectorParams
        if self.client.collection_exists(self.COLLECTION):
            info = self.client.get_collection(self.COLLECTION)
            existing_dim = info.config.params.vectors.size
            if existing_dim != self.DIM:
                self.client.delete_collection(self.COLLECTION)
        if not self.client.collection_exists(self.COLLECTION):
            self.client.create_collection(
                collection_name=self.COLLECTION,
                vectors_config=VectorParams(size=self.DIM, distance=Distance.COSINE),
            )

    def upsert_image(
        self,
        chunk_id: str,
        embedding: np.ndarray,
        label: str,
        source_doc: str,
        source_page: int,
        image_index: int,
        project_id: str = "default",
    ) -> None:
        from qdrant_client.models import PointStruct
        self.client.upsert(
            collection_name=self.COLLECTION,
            points=[PointStruct(
                id=_uid(chunk_id),
                vector=embedding.tolist(),
                payload={
                    "chunk_id": chunk_id,
                    "label": label,
                    "source_doc": source_doc,
                    "source_page": source_page,
                    "image_index": image_index,
                    "project_id": project_id,
                    "node_type": "image",
                },
            )],
        )

    def remove_chunk(self, chunk_id: str) -> None:
        self.client.delete(
            collection_name=self.COLLECTION,
            points_selector=[_uid(chunk_id)],
        )

    def search(
        self,
        query_vec: np.ndarray,
        top_k: int = 5,
        project_id: str = "default",
    ) -> list[dict]:
        from qdrant_client.models import Filter
        response = self.client.query_points(
            collection_name=self.COLLECTION,
            query=query_vec.tolist(),
            limit=top_k,
            query_filter=Filter(must=[_project_condition(project_id)]),
            with_payload=True,
        )
        return [{"payload": h.payload, "score": h.score} for h in response.points]

    def list_chunks(self, project_id: str = "default") -> list[dict]:
        from qdrant_client.models import Filter
        results, _ = self.client.scroll(
            collection_name=self.COLLECTION,
            scroll_filter=Filter(must=[_project_condition(project_id)]),
            with_payload=True,
            with_vectors=False,
            limit=1000,
        )
        return [p.payload for p in results]

    def clear(self, project_id: str = "default") -> None:
        from qdrant_client.models import Filter, FilterSelector
        self.client.delete(
            collection_name=self.COLLECTION,
            points_selector=FilterSelector(
                filter=Filter(must=[_project_condition(project_id)])
            ),
        )


# ── singleton ────────────────────────────────────────────────────────────────

import os as _os

_shared_client = None
_shared_client_lock = threading.Lock()
_store: QdrantStore | None = None
_image_store: ImageStore | None = None


def _get_shared_client():
    global _shared_client
    if _shared_client is not None:
        return _shared_client
    with _shared_client_lock:
        if _shared_client is None:
            from qdrant_client import QdrantClient
            url = _os.getenv("QDRANT_URL", "http://localhost:6333")
            path = _os.getenv("QDRANT_PATH", "")
            if path:
                _shared_client = QdrantClient(path=path)
            else:
                _shared_client = QdrantClient(url=url, timeout=5)
    return _shared_client


def get_store() -> QdrantStore:
    global _store
    if _store is None:
        url = _os.getenv("QDRANT_URL", "http://localhost:6333")
        path = _os.getenv("QDRANT_PATH", "")
        if path:
            _store = QdrantStore(path=path)
        else:
            _store = QdrantStore(url=url)
        # Inject shared client
        _store._client = _get_shared_client()
        _store._ensure_collection()
    return _store


def get_image_store() -> ImageStore:
    global _image_store
    if _image_store is None:
        url = _os.getenv("QDRANT_URL", "http://localhost:6333")
        path = _os.getenv("QDRANT_PATH", "")
        if path:
            _image_store = ImageStore(path=path)
        else:
            _image_store = ImageStore(url=url)
        # Inject shared client
        _image_store._client = _get_shared_client()
        _image_store._ensure_collection()
    return _image_store
