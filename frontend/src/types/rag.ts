// ── Core RAG types ────────────────────────────────────────────────────────────

export interface ChunkInfo {
  chunk_id: string
  text: string
  source_page: number
  start_char: number
  end_char: number
  source_doc: string
  source_anchor?: string | null
  label: string | null
  is_manual: boolean
}

export interface DocInfo {
  filename: string
  chunk_count: number
  region: string | null
  year: number | null
  perspective: string | null
}

export interface ProjectFilesResponse {
  files: DocInfo[]
  total_chunks: number
}

export interface DocMetadata {
  region?: string
  year?: number
  date?: string
  perspective?: string
}

export interface ProjectOption {
  value: string
  label: string
  metadata?: Record<string, unknown>
}

export interface ProjectFilterOptions {
  locations: ProjectOption[]
  dates: ProjectOption[]
  perspectives: ProjectOption[]
}

export interface IngestResponse {
  filename: string
  total_pages: number
  total_chunks: number
  chunks: ChunkInfo[]
}

export interface RetrievedChunk {
  chunk_id: string
  text: string
  source_page: number
  score: number
  source_doc: string
  source_anchor?: string | null
  label: string | null
  is_manual: boolean
  is_boosted: boolean
  node_type: 'auto' | 'manual' | 'relation' | string
  hazard_tags: string[]
}

export interface GraphNode {
  id: string
  label: string
  type: 'pdf' | 'chunk' | 'embedding' | 'faiss' | 'query' | 'llm' | 'answer'
  active: boolean
  data: Record<string, unknown>
}

export interface GraphEdge {
  source: string
  target: string
  label: string
  active: boolean
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface QueryResponse {
  question: string
  answer: string
  retrieved_chunks: RetrievedChunk[]
  graph_data: GraphData
  anomalies: Array<{ type: string; message: string; details: Record<string, unknown> }>
  router: Record<string, number>
}

// ── Manual chunk types ────────────────────────────────────────────────────────

export interface ManualChunkRequest {
  text: string
  label: string
  source_doc?: string
  source_page?: number
  source_anchor?: string | null
  project_id?: string
  region?: string
  year?: number
  perspective?: string
}

export interface ManualChunkInfo {
  chunk_id: string
  text: string
  label: string
  source_doc: string
  source_page: number
  source_anchor?: string | null
  project_id: string
  region: string | null
  year: number | null
  perspective: string | null
}

// ── Project types ─────────────────────────────────────────────────────────────

export interface Project {
  id: string
  name: string
  meta: DocMetadata
  createdAt: number
}

// ── Page types ────────────────────────────────────────────────────────────────

export interface PageText {
  page_num: number
  text: string
}

export interface PDFInfo {
  filename: string
  total_pages: number
}

export interface OCRWord {
  text: string
  left: number
  top: number
  width: number
  height: number
  conf: number
}

export interface OCRPage {
  page_num: number
  width: number
  height: number
  words: OCRWord[]
}

export interface VLMSelectionRequest {
  image_b64: string
  source_doc: string
  source_page: number
  project_id?: string
}

export interface VLMSelectionResponse {
  label: string
  description: string
  evidence_type: string
  source_doc: string
  source_page: number
}

// ── UMAP types ────────────────────────────────────────────────────────────────

export interface UMAPPoint {
  chunk_id: string
  x: number
  y: number
  text: string
  source_page: number
  source_doc: string
  label: string | null
  node_type: 'auto' | 'manual' | 'relation' | string
  is_retrieved: boolean
  is_manual: boolean
  score: number
}

export interface UMAPResponse {
  points: UMAPPoint[]
  query_x: number | null
  query_y: number | null
  query_label: string | null
}

// ── Graph analysis types ──────────────────────────────────────────────────────

export interface GraphAnalysisNode {
  id: string
  label: string
  keywords: string
  page: number
  source_doc: string
  node_type: 'auto' | 'manual' | 'relation' | 'image' | string
  hazard_tags: string[]
  project_id: string
  degree_centrality: number
  betweenness_centrality: number
  community: number
  text: string
  is_retrieved: boolean
  is_manual: boolean
}

export interface GraphAnalysisEdge {
  source: string
  target: string
  weight: number
}

export interface ChunkRelation {
  id: string
  from_chunk_id: string
  to_chunk_id: string
  label: string
  weight: number
  project_id: string
  created_at: number
  vectorized: boolean
}

export interface GraphAnalysisResponse {
  nodes: GraphAnalysisNode[]
  edges: GraphAnalysisEdge[]
  num_communities: number
  density: number
  manual_relations: ChunkRelation[]
}

export interface GraphJsonInfo {
  filename: string
  graph_name: string
  updated_at: number | null
  size_bytes: number
  node_count: number
  edge_count: number
}

export interface GraphJsonListResponse {
  files: GraphJsonInfo[]
}

export type VisualizationTab = 'graph-analysis' | 'knowledge-graph' | 'graph-json' | 'embedding-space'
