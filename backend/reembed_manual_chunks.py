"""
Re-embed existing manual chunks using "label: text" strategy.
Run once after upgrading to label-prefix embedding:

    python reembed_manual_chunks.py [project_id]
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QDRANT_PATH", "./qdrant_data")
from dotenv import load_dotenv
load_dotenv()

from rag.embedding import embed_query
from rag.qdrant_store import get_store, DocMeta

project_id = sys.argv[1] if len(sys.argv) > 1 else "default"
store = get_store()

payloads = store.manual_chunks(project_id=project_id)
if not payloads:
    print(f"No manual chunks found for project '{project_id}'")
    sys.exit(0)

print(f"Re-embedding {len(payloads)} manual chunks for project '{project_id}'...")

from qdrant_client.models import PointStruct
from rag.qdrant_store import _uid

points = []
for p in payloads:
    # Manual chunks use label as the semantic key — query matches labels,
    # chunk text is only used as detailed evidence in the LLM context.
    label = p.get("label") or p.get("chunk_id", "")
    vec = embed_query(label)

    points.append(PointStruct(
        id=_uid(p["chunk_id"]),
        vector=vec.tolist(),
        payload=p,
    ))
    print(f"  ✓ {p['chunk_id'][:50]}")

store.client.upsert(collection_name=store.COLLECTION, points=points)
print("Done.")
