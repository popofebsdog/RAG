from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from typing import Any, Iterable

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover - optional dependency when DATABASE_URL is unset
    psycopg = None
    dict_row = None
    Jsonb = None


def database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def is_configured() -> bool:
    return bool(database_url())


def is_enabled() -> bool:
    return bool(database_url()) and psycopg is not None


@contextmanager
def connect():
    if not is_enabled():
        raise RuntimeError("PostgreSQL is not enabled. Set DATABASE_URL.")
    conn = psycopg.connect(database_url(), row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema() -> None:
    if is_configured() and psycopg is None:
        raise RuntimeError("DATABASE_URL is set but psycopg is not installed. Run pip install -r requirements.txt.")
    if not is_enabled():
        return
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
              id TEXT PRIMARY KEY,
              name TEXT,
              metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS documents (
              id BIGSERIAL PRIMARY KEY,
              project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
              filename TEXT NOT NULL,
              region TEXT,
              year INTEGER,
              perspective TEXT,
              total_pages INTEGER,
              chunk_count INTEGER NOT NULL DEFAULT 0,
              metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              UNIQUE(project_id, filename)
            );

            CREATE TABLE IF NOT EXISTS chunks (
              chunk_id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
              document_id BIGINT REFERENCES documents(id) ON DELETE SET NULL,
              source_doc TEXT,
              source_page INTEGER NOT NULL DEFAULT 0,
              source_anchor TEXT,
              start_char INTEGER NOT NULL DEFAULT 0,
              end_char INTEGER NOT NULL DEFAULT 0,
              label TEXT,
              text TEXT NOT NULL,
              node_type TEXT NOT NULL DEFAULT 'auto',
              is_manual BOOLEAN NOT NULL DEFAULT false,
              hazard_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
              region TEXT,
              year INTEGER,
              perspective TEXT,
              metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS relations (
              id UUID PRIMARY KEY,
              project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
              from_chunk_id TEXT NOT NULL,
              to_chunk_id TEXT NOT NULL,
              label TEXT NOT NULL,
              weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
              vectorized BOOLEAN NOT NULL DEFAULT false,
              metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
              created_at BIGINT NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              CONSTRAINT relations_distinct_nodes CHECK (from_chunk_id <> to_chunk_id)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS relations_unique_from_to_label
              ON relations(project_id, from_chunk_id, to_chunk_id, lower(label));

            CREATE INDEX IF NOT EXISTS chunks_project_idx ON chunks(project_id);
            CREATE INDEX IF NOT EXISTS chunks_document_idx ON chunks(project_id, source_doc);
            CREATE INDEX IF NOT EXISTS relations_project_idx ON relations(project_id);
            CREATE INDEX IF NOT EXISTS relations_from_idx ON relations(project_id, from_chunk_id);
            CREATE INDEX IF NOT EXISTS relations_to_idx ON relations(project_id, to_chunk_id);

            CREATE TABLE IF NOT EXISTS graph_exports (
              id BIGSERIAL PRIMARY KEY,
              project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
              graph_name TEXT NOT NULL,
              filename TEXT NOT NULL,
              node_count INTEGER NOT NULL DEFAULT 0,
              edge_count INTEGER NOT NULL DEFAULT 0,
              metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              UNIQUE(project_id, filename)
            );

            CREATE TABLE IF NOT EXISTS query_logs (
              id BIGSERIAL PRIMARY KEY,
              project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
              question TEXT NOT NULL,
              answer TEXT NOT NULL,
              top_k INTEGER,
              router JSONB NOT NULL DEFAULT '{}'::jsonb,
              retrieved_chunks JSONB NOT NULL DEFAULT '[]'::jsonb,
              anomalies JSONB NOT NULL DEFAULT '[]'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )


def ensure_project(project_id: str, name: str | None = None, metadata: dict[str, Any] | None = None) -> None:
    if not is_enabled():
        return
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO projects(id, name, metadata)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
              name = COALESCE(EXCLUDED.name, projects.name),
              metadata = projects.metadata || EXCLUDED.metadata,
              updated_at = now()
            """,
            (project_id, name, Jsonb(metadata or {})),
        )


def upsert_document(
    project_id: str,
    filename: str,
    *,
    region: str | None = None,
    year: int | None = None,
    perspective: str | None = None,
    total_pages: int | None = None,
    chunk_count: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if not is_enabled() or not filename:
        return
    ensure_project(project_id)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO documents(project_id, filename, region, year, perspective, total_pages, chunk_count, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s, 0), %s)
            ON CONFLICT (project_id, filename) DO UPDATE SET
              region = COALESCE(EXCLUDED.region, documents.region),
              year = COALESCE(EXCLUDED.year, documents.year),
              perspective = COALESCE(EXCLUDED.perspective, documents.perspective),
              total_pages = COALESCE(EXCLUDED.total_pages, documents.total_pages),
              chunk_count = COALESCE(EXCLUDED.chunk_count, documents.chunk_count),
              metadata = documents.metadata || EXCLUDED.metadata,
              updated_at = now()
            """,
            (project_id, filename, region, year, perspective, total_pages, chunk_count, Jsonb(metadata or {})),
        )


def list_documents(project_id: str) -> list[dict]:
    if not is_enabled():
        return []
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT filename, region, year, perspective, total_pages, chunk_count
            FROM documents
            WHERE project_id = %s
            ORDER BY created_at, filename
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def remove_document(project_id: str, filename: str) -> None:
    if not is_enabled():
        return
    with connect() as conn:
        conn.execute("DELETE FROM documents WHERE project_id = %s AND filename = %s", (project_id, filename))


def clear_project(project_id: str) -> None:
    if not is_enabled():
        return
    ensure_project(project_id)
    with connect() as conn:
        conn.execute("DELETE FROM query_logs WHERE project_id = %s", (project_id,))
        conn.execute("DELETE FROM graph_exports WHERE project_id = %s", (project_id,))
        conn.execute("DELETE FROM relations WHERE project_id = %s", (project_id,))
        conn.execute("DELETE FROM chunks WHERE project_id = %s", (project_id,))
        conn.execute("DELETE FROM documents WHERE project_id = %s", (project_id,))


def bulk_upsert_chunks(project_id: str, payloads: Iterable[dict]) -> None:
    if not is_enabled():
        return
    ensure_project(project_id)
    payload_list = list(payloads)
    if not payload_list:
        return
    with connect() as conn:
        for p in payload_list:
            source_doc = p.get("source_doc") or ""
            if source_doc:
                conn.execute(
                    """
                    INSERT INTO documents(project_id, filename, region, year, perspective, chunk_count)
                    VALUES (%s, %s, %s, %s, %s, 0)
                    ON CONFLICT (project_id, filename) DO UPDATE SET updated_at = now()
                    """,
                    (project_id, source_doc, p.get("region"), p.get("year"), p.get("perspective")),
                )
            conn.execute(
                """
                INSERT INTO chunks(
                  chunk_id, project_id, document_id, source_doc, source_page, source_anchor,
                  start_char, end_char, label, text, node_type, is_manual, hazard_tags,
                  region, year, perspective, metadata
                )
                VALUES (
                  %(chunk_id)s, %(project_id)s,
                  (SELECT id FROM documents WHERE project_id = %(project_id)s AND filename = %(source_doc)s),
                  %(source_doc)s, %(source_page)s, %(source_anchor)s,
                  %(start_char)s, %(end_char)s, %(label)s, %(text)s, %(node_type)s, %(is_manual)s,
                  %(hazard_tags)s, %(region)s, %(year)s, %(perspective)s, %(metadata)s
                )
                ON CONFLICT (chunk_id) DO UPDATE SET
                  source_doc = EXCLUDED.source_doc,
                  document_id = EXCLUDED.document_id,
                  source_page = EXCLUDED.source_page,
                  source_anchor = EXCLUDED.source_anchor,
                  start_char = EXCLUDED.start_char,
                  end_char = EXCLUDED.end_char,
                  label = EXCLUDED.label,
                  text = EXCLUDED.text,
                  node_type = EXCLUDED.node_type,
                  is_manual = EXCLUDED.is_manual,
                  hazard_tags = EXCLUDED.hazard_tags,
                  region = EXCLUDED.region,
                  year = EXCLUDED.year,
                  perspective = EXCLUDED.perspective,
                  metadata = chunks.metadata || EXCLUDED.metadata,
                  updated_at = now()
                """,
                {
                    "chunk_id": p["chunk_id"],
                    "project_id": project_id,
                    "source_doc": source_doc,
                    "source_page": int(p.get("source_page") or 0),
                    "source_anchor": p.get("source_anchor"),
                    "start_char": int(p.get("start_char") or 0),
                    "end_char": int(p.get("end_char") or len(str(p.get("text") or ""))),
                    "label": p.get("label"),
                    "text": str(p.get("text") or ""),
                    "node_type": p.get("node_type") or "auto",
                    "is_manual": bool(p.get("is_manual")),
                    "hazard_tags": Jsonb(list(p.get("hazard_tags") or [])),
                    "region": p.get("region"),
                    "year": p.get("year"),
                    "perspective": p.get("perspective"),
                    "metadata": Jsonb(p.get("metadata") or {}),
                },
            )
        conn.execute(
            """
            UPDATE documents d
            SET chunk_count = counts.count, updated_at = now()
            FROM (
              SELECT project_id, source_doc, count(*) AS count
              FROM chunks
              WHERE project_id = %s AND COALESCE(source_doc, '') <> '' AND node_type <> 'relation'
              GROUP BY project_id, source_doc
            ) counts
            WHERE d.project_id = counts.project_id AND d.filename = counts.source_doc
            """,
            (project_id,),
        )


def remove_chunk(chunk_id: str) -> None:
    if not is_enabled():
        return
    with connect() as conn:
        conn.execute("DELETE FROM chunks WHERE chunk_id = %s", (chunk_id,))


def remove_chunks_for_document(project_id: str, filename: str) -> set[str]:
    if not is_enabled():
        return set()
    with connect() as conn:
        rows = conn.execute(
            "DELETE FROM chunks WHERE project_id = %s AND source_doc = %s RETURNING chunk_id",
            (project_id, filename),
        ).fetchall()
    return {row["chunk_id"] for row in rows}


def list_relations(project_id: str) -> list[dict]:
    if not is_enabled():
        return []
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id::text AS id, from_chunk_id, to_chunk_id, label, weight, project_id,
                   created_at, vectorized
            FROM relations
            WHERE project_id = %s
            ORDER BY created_at, id
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def add_relation(from_chunk_id: str, to_chunk_id: str, label: str, project_id: str, weight: float = 1.0) -> dict:
    if not is_enabled():
        raise RuntimeError("PostgreSQL is not enabled")
    import uuid

    ensure_project(project_id)
    created_at = int(time.time())
    relation_id = str(uuid.uuid4())
    with connect() as conn:
        row = conn.execute(
            """
            INSERT INTO relations(id, project_id, from_chunk_id, to_chunk_id, label, weight, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (project_id, from_chunk_id, to_chunk_id, lower(label)) DO NOTHING
            RETURNING id::text AS id, from_chunk_id, to_chunk_id, label, weight, project_id, created_at, vectorized
            """,
            (relation_id, project_id, from_chunk_id, to_chunk_id, label, max(0.0, min(1.0, weight)), created_at),
        ).fetchone()
        if row is None:
            row = conn.execute(
                """
                SELECT id::text AS id, from_chunk_id, to_chunk_id, label, weight, project_id, created_at, vectorized
                FROM relations
                WHERE project_id = %s AND from_chunk_id = %s AND to_chunk_id = %s AND lower(label) = lower(%s)
                """,
                (project_id, from_chunk_id, to_chunk_id, label),
            ).fetchone()
    return dict(row)


def set_relation_vectorized(relation_id: str, vectorized: bool = True) -> None:
    if not is_enabled():
        return
    with connect() as conn:
        conn.execute("UPDATE relations SET vectorized = %s, updated_at = now() WHERE id = %s", (vectorized, relation_id))


def update_relation_weight(relation_id: str, weight: float, project_id: str) -> bool:
    if not is_enabled():
        return False
    with connect() as conn:
        row = conn.execute(
            """
            UPDATE relations
            SET weight = %s, updated_at = now()
            WHERE id = %s AND project_id = %s
            RETURNING id
            """,
            (max(0.0, min(1.0, weight)), relation_id, project_id),
        ).fetchone()
    return row is not None


def remove_relation(relation_id: str, project_id: str) -> bool:
    if not is_enabled():
        return False
    with connect() as conn:
        row = conn.execute(
            "DELETE FROM relations WHERE id = %s AND project_id = %s RETURNING id",
            (relation_id, project_id),
        ).fetchone()
    return row is not None


def clear_relations(project_id: str) -> None:
    if not is_enabled():
        return
    with connect() as conn:
        conn.execute("DELETE FROM relations WHERE project_id = %s", (project_id,))


def remove_relations_for_chunks(chunk_ids: set[str], project_id: str) -> list[str]:
    if not is_enabled() or not chunk_ids:
        return []
    with connect() as conn:
        rows = conn.execute(
            """
            DELETE FROM relations
            WHERE project_id = %s AND (from_chunk_id = ANY(%s) OR to_chunk_id = ANY(%s))
            RETURNING id::text AS id
            """,
            (project_id, list(chunk_ids), list(chunk_ids)),
        ).fetchall()
    return [row["id"] for row in rows]


def save_graph_export(project_id: str, graph_name: str, filename: str, data: dict[str, Any]) -> None:
    if not is_enabled():
        return
    ensure_project(project_id)
    nodes = data.get("nodes") or []
    edges = data.get("edges") or data.get("relations") or []
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO graph_exports(project_id, graph_name, filename, node_count, edge_count, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (project_id, filename) DO UPDATE SET
              graph_name = EXCLUDED.graph_name,
              node_count = EXCLUDED.node_count,
              edge_count = EXCLUDED.edge_count,
              metadata = EXCLUDED.metadata,
              updated_at = now()
            """,
            (project_id, graph_name, filename, len(nodes), len(edges), Jsonb({"stored_as": "json_file"})),
        )


def save_query_log(
    project_id: str,
    question: str,
    answer: str,
    *,
    top_k: int | None = None,
    router: dict[str, Any] | None = None,
    retrieved_chunks: list[dict] | None = None,
    anomalies: list[dict] | None = None,
) -> None:
    if not is_enabled():
        return
    ensure_project(project_id)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO query_logs(project_id, question, answer, top_k, router, retrieved_chunks, anomalies)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                project_id,
                question,
                answer,
                top_k,
                Jsonb(router or {}),
                Jsonb(retrieved_chunks or []),
                Jsonb(anomalies or []),
            ),
        )
