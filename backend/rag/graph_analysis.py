from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
import numpy as np

from .chunking import Chunk


@dataclass
class GraphNodeData:
    id: str
    label: str
    page: int
    degree_centrality: float
    betweenness_centrality: float
    community: int
    text: str


@dataclass
class GraphEdgeData:
    source: str
    target: str
    weight: float


@dataclass
class GraphAnalysisResult:
    nodes: list[GraphNodeData]
    edges: list[GraphEdgeData]
    num_communities: int
    density: float


def build_similarity_graph(
    chunks: list[Chunk],
    embeddings: np.ndarray,
    threshold: float = 0.5,
    retrieved_ids: set[str] | None = None,
    manual_relation_pairs: list[tuple[str, str, float]] | None = None,
) -> GraphAnalysisResult:
    n = len(chunks)
    sim_matrix = embeddings @ embeddings.T  # cosine (already normalized)

    G = nx.Graph()
    for i, chunk in enumerate(chunks):
        G.add_node(chunk.chunk_id, page=chunk.source_page, text=chunk.text[:200])

    for i in range(n):
        for j in range(i + 1, n):
            sim = float(sim_matrix[i, j])
            if sim >= threshold:
                G.add_edge(chunks[i].chunk_id, chunks[j].chunk_id, weight=sim)

    # Add manual relations as edges (weight=1.0) so they influence centrality/density
    node_ids = set(G.nodes)
    for from_id, to_id, weight in (manual_relation_pairs or []):
        if from_id in node_ids and to_id in node_ids:
            if not G.has_edge(from_id, to_id):
                G.add_edge(from_id, to_id, weight=max(0.0, min(1.0, weight)))

    degree_c = nx.degree_centrality(G)
    try:
        between_c = nx.betweenness_centrality(G, weight="weight", normalized=True)
    except Exception:
        between_c = {n: 0.0 for n in G.nodes}

    # Community detection
    try:
        communities_gen = nx.community.greedy_modularity_communities(G, weight="weight")
        communities = list(communities_gen)
        community_map: dict[str, int] = {}
        for idx, comm in enumerate(communities):
            for node in comm:
                community_map[node] = idx
    except Exception:
        community_map = {node: 0 for node in G.nodes}

    nodes = [
        GraphNodeData(
            id=chunk.chunk_id,
            label=f"p{chunk.source_page}\n{chunk.chunk_id}",
            page=chunk.source_page,
            degree_centrality=round(degree_c.get(chunk.chunk_id, 0.0), 4),
            betweenness_centrality=round(between_c.get(chunk.chunk_id, 0.0), 4),
            community=community_map.get(chunk.chunk_id, 0),
            text=chunk.text[:300],
        )
        for chunk in chunks
    ]

    edges = [
        GraphEdgeData(
            source=u,
            target=v,
            weight=round(data["weight"], 4),
        )
        for u, v, data in G.edges(data=True)
    ]

    density = round(nx.density(G), 4)

    return GraphAnalysisResult(
        nodes=nodes,
        edges=edges,
        num_communities=len(set(community_map.values())),
        density=density,
    )
