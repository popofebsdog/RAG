import { ref, computed } from 'vue'
import axios from 'axios'
import type {
  IngestResponse,
  QueryResponse,
  UMAPResponse,
  GraphAnalysisResponse,
  DocInfo,
  ProjectFilesResponse,
  DocMetadata,
  ManualChunkInfo,
  ManualChunkRequest,
  PDFInfo,
  PageText,
  OCRPage,
  VLMSelectionRequest,
  VLMSelectionResponse,
  Project,
  ChunkRelation,
} from '../types/rag'

const BASE = '/api'
const PROJECTS_KEY = 'rag_projects'
const ACTIVE_PROJECT_KEY = 'rag_active_project'

function loadProjects(): Project[] {
  try {
    const raw = localStorage.getItem(PROJECTS_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveProjects(ps: Project[]) {
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(ps))
}

function apiErrorMessage(e: unknown, fallback = 'Unknown error'): string {
  return axios.isAxiosError(e) ? (e.response?.data?.detail ?? e.message) : fallback
}

function isNoDocumentIndexed(e: unknown): boolean {
  return /No document indexed/i.test(apiErrorMessage(e, ''))
}

export function useRag() {
  const ingesting = ref(false)
  const querying = ref(false)
  const loadingUmap = ref(false)
  const loadingGraphAnalysis = ref(false)

  const ingestResult = ref<IngestResponse | null>(null)
  const queryResult = ref<QueryResponse | null>(null)
  const umapResult = ref<UMAPResponse | null>(null)
  const graphAnalysisResult = ref<GraphAnalysisResponse | null>(null)
  const projectFiles = ref<DocInfo[]>([])
  const manualChunks = ref<ManualChunkInfo[]>([])
  const error = ref<string | null>(null)
  const sourceVersion = ref(Date.now())

  // ── project management ────────────────────────────────────────────────────

  const projects = ref<Project[]>(loadProjects())
  const relations = ref<ChunkRelation[]>([])
  const activeProjectId = ref<string | null>(
    localStorage.getItem(ACTIVE_PROJECT_KEY) || (projects.value[0]?.id ?? null),
  )

  const activeProject = computed<Project | null>(
    () => projects.value.find((p) => p.id === activeProjectId.value) ?? null,
  )

  function resetProjectScopedState() {
    ingestResult.value = null
    queryResult.value = null
    umapResult.value = null
    graphAnalysisResult.value = null
    projectFiles.value = []
    manualChunks.value = []
    relations.value = []
    error.value = null
    sourceVersion.value = Date.now()
  }

  function createProject(name: string, meta: DocMetadata): Project {
    const project: Project = {
      id: `proj_${Date.now()}`,
      name: name.trim(),
      meta,
      createdAt: Date.now(),
    }
    projects.value.push(project)
    saveProjects(projects.value)
    switchProject(project.id)
    return project
  }

  function switchProject(id: string) {
    if (activeProjectId.value === id) return
    activeProjectId.value = id
    localStorage.setItem(ACTIVE_PROJECT_KEY, id)
    resetProjectScopedState()
  }

  function deleteProject(id: string) {
    projects.value = projects.value.filter((p) => p.id !== id)
    saveProjects(projects.value)
    if (activeProjectId.value === id) {
      const next = projects.value[0]?.id ?? null
      activeProjectId.value = next
      if (next) localStorage.setItem(ACTIVE_PROJECT_KEY, next)
      else localStorage.removeItem(ACTIVE_PROJECT_KEY)
      resetProjectScopedState()
    }
  }

  function updateProject(id: string, name: string, meta: DocMetadata) {
    const idx = projects.value.findIndex((p) => p.id === id)
    if (idx !== -1) {
      projects.value[idx] = { ...projects.value[idx], name, meta }
      saveProjects(projects.value)
    }
  }

  // ── project files ─────────────────────────────────────────────────────────

  async function fetchProjectFiles(): Promise<void> {
    const projectId = activeProjectId.value
    if (!projectId) return
    try {
      const { data } = await axios.get<ProjectFilesResponse>(`${BASE}/project/files`, {
        params: { project_id: projectId },
      })
      if (activeProjectId.value !== projectId) return
      projectFiles.value = data.files
    } catch {
      // silent
    }
  }

  async function removeProjectFile(filename: string): Promise<void> {
    if (!activeProjectId.value) return
    try {
      await axios.delete(`${BASE}/project/files/${encodeURIComponent(filename)}`, {
        params: { project_id: activeProjectId.value },
      })
      sourceVersion.value = Date.now()
      ingestResult.value = null
      queryResult.value = null
      umapResult.value = null
      graphAnalysisResult.value = null
      await fetchProjectFiles()
      await fetchManualChunks()
      await fetchRelations()
      if (projectFiles.value.length === 0) {
        manualChunks.value = []
        relations.value = []
      } else {
        await fetchGraphAnalysis(undefined, 5, 0.5)
      }
    } catch (e: unknown) {
      error.value = apiErrorMessage(e)
    }
  }

  async function clearProject(): Promise<void> {
    if (!activeProjectId.value) return
    try {
      await axios.delete(`${BASE}/project/clear`, {
        params: { project_id: activeProjectId.value },
      })
      resetProjectScopedState()
    } catch (e: unknown) {
      error.value = apiErrorMessage(e)
    }
  }

  async function fetchPages(filename: string): Promise<PageText[]> {
    const { data } = await axios.get<PageText[]>(
      `${BASE}/project/pages/${encodeURIComponent(filename)}`,
      { params: { project_id: activeProjectId.value } },
    )
    return data
  }

  async function fetchPdfInfo(filename: string): Promise<PDFInfo> {
    const { data } = await axios.get<PDFInfo>(
      `${BASE}/project/files/${encodeURIComponent(filename)}/info`,
      { params: { project_id: activeProjectId.value } },
    )
    return data
  }

  async function fetchOcrPages(filename: string): Promise<OCRPage[]> {
    const { data } = await axios.get<OCRPage[]>(
      `${BASE}/project/files/${encodeURIComponent(filename)}/ocr`,
      { params: { project_id: activeProjectId.value } },
    )
    return data
  }

  function pdfUrl(filename: string): string {
    const params = new URLSearchParams({
      project_id: activeProjectId.value ?? 'default',
      v: String(sourceVersion.value),
    })
    return `${BASE}/project/files/${encodeURIComponent(filename)}/pdf?${params.toString()}`
  }

  function pageImageUrl(filename: string, pageNum: number): string {
    const params = new URLSearchParams({
      project_id: activeProjectId.value ?? 'default',
      v: String(sourceVersion.value),
    })
    return `${BASE}/project/files/${encodeURIComponent(filename)}/page-image/${pageNum}.png?${params.toString()}`
  }

  async function analyzeSelection(req: VLMSelectionRequest): Promise<VLMSelectionResponse> {
    try {
      const { data } = await axios.post<VLMSelectionResponse>(`${BASE}/vlm/selection`, {
        ...req,
        project_id: activeProjectId.value ?? 'default',
      })
      return data
    } catch (e: unknown) {
      const message = axios.isAxiosError(e) ? (e.response?.data?.detail ?? e.message) : 'VLM 辨識失敗'
      throw new Error(message)
    }
  }

  // ── ingest ────────────────────────────────────────────────────────────────

  async function ingestPdf(
    file: File,
    loaderType = 'auto',
    strategy: 'auto' | 'manual' = 'auto',
  ): Promise<void> {
    if (!activeProjectId.value) return
    ingesting.value = true
    error.value = null

    const project = activeProject.value
    const form = new FormData()
    form.append('file', file)
    form.append('loader_type', loaderType)
    form.append('chunk_strategy', strategy)
    form.append('mode', 'append')
    form.append('project_id', activeProjectId.value)
    form.append('region', project?.meta.region ?? '')
    form.append('year', project?.meta.year != null ? String(project.meta.year) : '')
    form.append('perspective', project?.meta.perspective ?? '')

    try {
      const { data } = await axios.post<IngestResponse>(`${BASE}/ingest`, form)
      ingestResult.value = data
      sourceVersion.value = Date.now()
      queryResult.value = null
      umapResult.value = null
      graphAnalysisResult.value = null
      await fetchProjectFiles()
      await fetchManualChunks()
      await fetchRelations()
      await fetchGraphAnalysis(undefined, 5, 0.5)
    } catch (e: unknown) {
      error.value = apiErrorMessage(e)
    } finally {
      ingesting.value = false
    }
  }

  // ── manual chunks ─────────────────────────────────────────────────────────

  async function fetchManualChunks(): Promise<void> {
    const projectId = activeProjectId.value
    if (!projectId) return
    try {
      const { data } = await axios.get<ManualChunkInfo[]>(`${BASE}/chunks/manual`, {
        params: { project_id: projectId },
      })
      if (activeProjectId.value !== projectId) return
      manualChunks.value = data
    } catch {
      // silent
    }
  }

  async function createManualChunk(req: ManualChunkRequest): Promise<ManualChunkInfo> {
    const { data } = await axios.post<ManualChunkInfo>(`${BASE}/chunks/manual`, {
      ...req,
      project_id: activeProjectId.value ?? 'default',
    })
    await fetchManualChunks()
    return data
  }

  async function deleteManualChunk(chunkId: string): Promise<void> {
    await axios.delete(`${BASE}/chunks/manual/${encodeURIComponent(chunkId)}`, {
      params: { project_id: activeProjectId.value ?? 'default' },
    })
    await fetchManualChunks()
    await fetchRelations()
  }

  async function fetchRelations(): Promise<void> {
    const projectId = activeProjectId.value
    if (!projectId) return
    try {
      const { data } = await axios.get<ChunkRelation[]>(`${BASE}/chunks/relations`, {
        params: { project_id: projectId },
      })
      if (activeProjectId.value !== projectId) return
      relations.value = data
    } catch {
      // silent
    }
  }

  async function createRelation(
    fromChunkId: string,
    toChunkId: string,
    label: string,
    weight = 1.0,
  ): Promise<ChunkRelation> {
    const { data } = await axios.post<ChunkRelation>(`${BASE}/chunks/relations`, {
      from_chunk_id: fromChunkId,
      to_chunk_id: toChunkId,
      label,
      weight,
      project_id: activeProjectId.value ?? 'default',
    })
    await fetchRelations()
    return data
  }

  async function updateRelationWeight(relationId: string, weight: number): Promise<ChunkRelation> {
    const { data } = await axios.patch<ChunkRelation>(
      `${BASE}/chunks/relations/${encodeURIComponent(relationId)}/weight`,
      { weight },
      { params: { project_id: activeProjectId.value ?? 'default' } },
    )
    await fetchRelations()
    return data
  }

  async function deleteRelation(relationId: string): Promise<void> {
    await axios.delete(`${BASE}/chunks/relations/${encodeURIComponent(relationId)}`, {
      params: { project_id: activeProjectId.value },
    })
    await fetchRelations()
  }

  // ── query ─────────────────────────────────────────────────────────────────

  async function query(
    question: string,
    topK = 5,
    region?: string,
    year?: number,
  ): Promise<void> {
    const projectId = activeProjectId.value ?? 'default'
    querying.value = true
    error.value = null
    try {
      const { data } = await axios.post<QueryResponse>(`${BASE}/query`, {
        question,
        top_k: topK,
        region: region ?? null,
        year: year ?? null,
        project_id: projectId,
      })
      if (activeProjectId.value !== projectId) return
      queryResult.value = data
    } catch (e: unknown) {
      error.value = apiErrorMessage(e)
    } finally {
      querying.value = false
    }
  }

  // ── umap ─────────────────────────────────────────────────────────────────

  async function fetchUmap(question?: string, topK = 5): Promise<void> {
    const projectId = activeProjectId.value ?? 'default'
    loadingUmap.value = true
    try {
      const { data } = await axios.post<UMAPResponse>(`${BASE}/umap`, {
        question: question ?? null,
        top_k: topK,
        project_id: projectId,
      })
      if (activeProjectId.value !== projectId) return
      umapResult.value = data
    } catch (e: unknown) {
      if (isNoDocumentIndexed(e)) {
        umapResult.value = null
      } else {
        error.value = apiErrorMessage(e)
      }
    } finally {
      loadingUmap.value = false
    }
  }

  // ── graph analysis ────────────────────────────────────────────────────────

  async function fetchGraphAnalysis(question?: string, topK = 5, threshold = 0.5): Promise<void> {
    const projectId = activeProjectId.value ?? 'default'
    loadingGraphAnalysis.value = true
    try {
      const { data } = await axios.post<GraphAnalysisResponse>(`${BASE}/graph-analysis`, {
        question: question ?? null,
        top_k: topK,
        threshold,
        project_id: projectId,
      })
      if (activeProjectId.value !== projectId) return
      graphAnalysisResult.value = data
    } catch (e: unknown) {
      if (isNoDocumentIndexed(e)) {
        graphAnalysisResult.value = null
      } else {
        error.value = apiErrorMessage(e)
      }
    } finally {
      loadingGraphAnalysis.value = false
    }
  }

  return {
    ingesting,
    querying,
    loadingUmap,
    loadingGraphAnalysis,
    ingestResult,
    queryResult,
    umapResult,
    graphAnalysisResult,
    projectFiles,
    manualChunks,
    error,
    projects,
    activeProjectId,
    activeProject,
    createProject,
    switchProject,
    deleteProject,
    updateProject,
    ingestPdf,
    removeProjectFile,
    clearProject,
    fetchProjectFiles,
    fetchPages,
    fetchPdfInfo,
    fetchOcrPages,
    pdfUrl,
    pageImageUrl,
    analyzeSelection,
    createManualChunk,
    deleteManualChunk,
    fetchManualChunks,
    relations,
    fetchRelations,
    createRelation,
    updateRelationWeight,
    deleteRelation,
    query,
    fetchUmap,
    fetchGraphAnalysis,
  }
}
