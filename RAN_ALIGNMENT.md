# RAN / MoR / Anomaly Alignment

This project can satisfy the proposed RAN module by treating manual nodes and
manual relations as supervised attention signals.

## Proposal Mapping

| Proposal Requirement | System Implementation |
| --- | --- |
| Text data import | PDF upload with PyMuPDF4LLM parsing |
| Text preprocessing, tokenization, serialization | Markdown extraction, page cache, semantic chunking |
| Build RNN/RAN base | Manual nodes act as attention anchors over chunk embeddings |
| Introduce attention mechanism | Manual relation edges and relation weights bias retrieval |
| Stable RAN network relation | Relation cache + Qdrant relation vectors + graph analysis |
| Graph structure and relation database | Qdrant payloads, relation store, Cytoscape graph views |
| Input anomaly judgment | Out-of-domain, relation contradiction, graph baseline anomaly |
| Result export / integration | Query response includes answer, evidence, graph, router, anomalies |

## Custom Node Integration

Custom nodes are no longer display-only:

- Manual text nodes are embedded into Qdrant using `label + selected text`.
- Manual relations are also embedded into Qdrant as synthetic `relation:*` nodes.
- Relation `weight` is persisted and affects retrieval expansion and graph analysis.
- Hazard tags are inferred for auto chunks, manual nodes, and relation nodes.

## Revised Production Goal

The current build target is:

1. **Project isolation**: each project owns an independent knowledge graph through `project_id`.
2. **Document integration inside a project**: all PDFs under the same project share one graph space.
3. **Unified node model**: auto chunks, manual chunks, relation nodes, and image nodes are queryable graph nodes.
4. **Manual attention**: user-defined nodes and weighted relations act as RAN attention anchors.
5. **MoR hazard routing**: hazard tags and router scores bias retrieval toward earthquake, flood, landslide, tsunami, and damage evidence.
6. **GNN-ready anomaly detection**: graph baseline now, GNN detector later when enough graph data exists.

## Auto / Manual Chunk Integration

Auto chunks and manual chunks are integrated in one Qdrant collection:

| Node Kind | Source | Role |
| --- | --- | --- |
| `auto` | parser + semantic chunker | broad evidence coverage |
| `manual` | user selection | high-precision attention node |
| `relation` | user-created relation edge | searchable causal / semantic relation |
| `image` | extracted image chunk | multimodal evidence node |

The graph analysis API now returns `source_doc`, `node_type`, `hazard_tags`, and
`project_id` for each node. This lets the UI show a single integrated project
graph while preserving document provenance.

## Project / Document Scope

- **Across projects**: graphs stay independent by default through `project_id`.
- **Within a project**: chunks and nodes from different documents are integrated into the same graph.
- **Future option**: add a global archive scope after the current-project workflow is stable.

## MoR Integration

The query router estimates hazard relevance for:

- earthquake
- flood
- landslide
- tsunami
- damage

Retrieval scores are adjusted by matching hazard tags. If a custom node or
relation node is retrieved, the linked neighbors are expanded into the final
evidence set using the manual relation weight.

## GNN Positioning

The current implementation is GNN-ready but does not require a trained GNN for
the first-week demo. The practical path is:

1. Rule-based anomaly checks
2. Graph statistics anomaly checks
3. PyGOD / PyTorch Geometric graph autoencoder after enough project data exists

This keeps the demo stable while preserving a credible upgrade path.

## PDF Parser Decision

The parser is standardized on PyMuPDF4LLM because it is RAG-oriented, converts
PDFs to Markdown, supports tables, and is lighter to run locally than Docling,
Marker, or Unstructured high-resolution pipelines.
