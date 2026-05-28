<template>
  <div class="h-screen w-screen flex flex-col overflow-hidden" style="background:#F4F1EB;color:#2C2926">

    <!-- ── Top bar ─────────────────────────────────────────────────────── -->
    <header class="h-[52px] shrink-0 flex items-center border-b px-4 gap-4" style="background:#FDFCF9;border-color:#E0DBD2">
      <!-- Project tag -->
      <div class="flex-1 flex items-center gap-2.5 min-w-0">
        <div v-if="activeProject" class="flex items-center gap-2 min-w-0">
          <div class="w-2 h-2 rounded-full bg-n2 shrink-0" />
          <span class="font-serif text-[15px] leading-none truncate" style="color:#2C2926">{{ activeProject.name }}</span>
          <span v-if="activeProject.meta.region || activeProject.meta.date || activeProject.meta.year" class="text-[11px] bg-black/[0.06] px-2 py-0.5 rounded shrink-0" style="color:#A9A39A">
            {{ [activeProject.meta.region, activeProject.meta.date || activeProject.meta.year].filter(Boolean).join(' · ') }}
          </span>
        </div>
        <div v-else class="text-[13px] font-medium" style="color:#A9A39A">Visual RAG System</div>
      </div>

      <!-- Document Reader -->
      <button
        v-if="projectFiles.length > 0"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-all"
        :style="showReader ? { background: '#2C2926', color: '#fff' } : { background: 'rgba(0,0,0,0.06)', color: '#6B6660' }"
        @click="showReader = true"
      >
        <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <path d="M4 2h6l3 3v9H4zM9 2v3h3M6 8h5M6 10.5h3"/>
        </svg>
        {{ lang === 'zh' ? '原文' : 'Source' }}
        <span v-if="manualChunks.length > 0" class="bg-black/20 rounded px-1 py-px text-[9px]">{{ manualChunks.length }}</span>
      </button>

      <!-- Ask / Chat toggle -->
      <button
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-all"
        :style="chatOpen ? { background: '#2C2926', color: '#fff' } : { background: 'rgba(0,0,0,0.06)', color: '#6B6660' }"
        @click="chatOpen = !chatOpen"
      >
        <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <path d="M2 3h12v8H9l-3 3V11H2z"/>
        </svg>
        {{ lang === 'zh' ? '詢問' : 'Ask' }}
      </button>

      <!-- Language toggle -->
      <button
        class="px-3 py-1 rounded-lg text-[11px] font-medium border transition-all tracking-wide"
        style="border-color:#E0DBD2;color:#6B6660"
        @click="lang = lang === 'en' ? 'zh' : 'en'"
      >{{ lang === 'en' ? '中文' : 'EN' }}</button>
    </header>

    <!-- ── Body ────────────────────────────────────────────────────────── -->
    <div class="flex-1 flex overflow-hidden">

      <!-- Left Rail (collapsible) -->
      <aside
        class="shrink-0 flex flex-col border-r overflow-hidden transition-[width] duration-[250ms] ease-[cubic-bezier(0.4,0,0.2,1)]"
        :style="{ width: railOpen ? '260px' : '52px', background: '#F8FAFC', borderColor: '#D7DEE8' }"
      >
        <!-- Rail header -->
        <div class="h-[52px] shrink-0 flex items-center border-b"
          style="border-color:#D7DEE8"
          :class="railOpen ? 'px-4 justify-between' : 'justify-center'">
          <button
            class="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-black/[0.06] transition-colors"
            @click="railOpen = !railOpen"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#6B6660" stroke-width="1.5" stroke-linecap="round">
              <path d="M2 4h12M2 8h12M2 12h12"/>
            </svg>
          </button>
          <span v-if="railOpen" class="text-[12px] font-semibold tracking-tight" style="color:#172033">{{ lang === 'zh' ? '工作區' : 'Workspace' }}</span>
        </div>

        <!-- Rail content (only when expanded) -->
        <div v-if="railOpen" class="flex-1 overflow-y-auto p-2 space-y-3">

          <!-- Projects section -->
          <div>
            <p class="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em]" style="color:#A9A39A">
              {{ lang === 'zh' ? '專案' : 'Projects' }}
            </p>
            <ProjectPanel
              :projects="projects"
              :active-project-id="activeProjectId"
              :filter-options="projectFilterOptions"
              :preview-external-vision="fetchExternalVisionPreview"
              :lang="lang"
              @create="onCreateProject"
              @switch="onSwitchProject"
              @delete="onDeleteProject"
            />
          </div>

          <div v-if="activeProject" class="h-px mx-2" style="background:#D7DEE8" />

          <!-- Upload + PDF parser (when project selected) -->
          <template v-if="activeProject">
            <UploadPanel
              :ingesting="ingesting"
              :ingest-result="ingestResult"
              :has-pending-preview="Boolean(ingestPreview)"
              :error="uploadError"
              :lang="lang"
              @upload="handleUpload"
              @review="reviewPanelOpen = true"
            />

            <!-- File list -->
            <div v-if="projectFiles.length > 0">
              <p class="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] flex items-center justify-between" style="color:#A9A39A">
                <span>{{ lang === 'zh' ? '檔案' : 'Files' }}</span>
                <button class="text-[10px] hover:text-red-500 transition-colors normal-case tracking-normal" style="color:#A9A39A" @click="requestClearProject">
                  {{ lang === 'zh' ? '清除' : 'Clear' }}
                </button>
              </p>
              <div class="space-y-0.5">
                <div
                  v-for="doc in projectFiles" :key="doc.filename"
                  class="flex items-center gap-2 px-2.5 py-2 rounded-lg border group transition-colors"
                  style="background:#FFFFFF;border-color:#D7DEE8"
                >
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="#A9A39A" stroke-width="1.5" stroke-linecap="round" class="shrink-0">
                    <path d="M4 2h6l3 3v9H4zM9 2v3h3M6 8h5M6 10.5h3"/>
                  </svg>
                  <div class="min-w-0 flex-1">
                    <p class="text-[12px] font-semibold truncate" style="color:#172033" :title="doc.filename">{{ doc.filename }}</p>
                    <p class="text-[11px]" style="color:#667085">
                      {{ doc.chunk_count > 0 ? `${doc.chunk_count} ${lang === 'zh' ? '知識節點' : 'knowledge nodes'}` : (lang === 'zh' ? '待建立知識圖譜' : 'pending knowledge graph') }}
                    </p>
                  </div>
                  <button
                    class="opacity-0 group-hover:opacity-100 hover:text-red-400 text-xs transition-all shrink-0"
                    style="color:#A9A39A"
                    @click="requestRemoveProjectFile(doc.filename)"
                  >✕</button>
                </div>
              </div>
            </div>
          </template>

        </div>

        <!-- Collapsed rail: icon-only project dots -->
        <div v-else class="flex-1 flex flex-col items-center pt-3 gap-2">
          <div
            v-for="p in projects" :key="p.id"
            class="w-8 h-8 rounded-lg flex items-center justify-center cursor-pointer transition-colors"
            :class="activeProjectId === p.id ? 'shadow-sm' : 'hover:bg-black/[0.06]'"
            :style="activeProjectId === p.id ? { background: '#FFFFFF', border: '1px solid #D7DEE8' } : {}"
            :title="p.name"
            @click="p.id !== activeProjectId && onSwitchProject(p.id)"
          >
            <div class="w-2 h-2 rounded-full" :style="{ background: p.id === activeProjectId ? '#6B6660' : '#A9A39A' }" />
          </div>
        </div>
      </aside>

      <!-- Center canvas -->
      <main class="flex-1 overflow-hidden dot-grid relative">
        <VisualizationPanel
          :has-content="hasContent"
          :umap-result="umapResult"
          :graph-analysis-result="graphAnalysisResult"
          :query-result="queryResult"
          :manual-chunks="manualChunks"
          :relations="relations"
          :project-id="activeProjectId"
          :project-name="activeProject?.name ?? ''"
          :loading-umap="loadingUmap"
          :loading-graph-analysis="loadingGraphAnalysis"
          :lang="lang"
          :pdf-url="pdfUrl"
          :page-image-url="pageImageUrl"
          :create-relation="handleCreateRelation"
          :update-relation-weight="handleUpdateRelationWeight"
          :delete-relation="handleDeleteRelation"
          class="w-full h-full"
          @fetch-umap="fetchUmap"
          @fetch-graph-analysis="handleFetchGraphAnalysis"
          @view-source="openReaderAtSource"
        />
        <NodeReviewPanel
          v-if="ingestPreview && reviewPanelOpen"
          :preview="ingestPreview"
          :busy="ingesting"
          :lang="lang"
          @confirm="handleCommitIngestPreview"
          @discard="handleDiscardIngestPreview"
          @close="reviewPanelOpen = false"
        />
      </main>

      <!-- Right chat panel -->
      <aside
        class="shrink-0 flex flex-col border-l overflow-hidden transition-[width] duration-[250ms] ease-[cubic-bezier(0.4,0,0.2,1)]"
        style="border-color:#E0DBD2"
        :style="{ width: chatOpen ? '300px' : '0px', background: '#FDFCF9' }"
      >
        <ChatPanel
          :can-query="hasContent && !ingesting"
          :querying="querying"
          :query-result="queryResult"
          :error="queryError"
          :lang="lang"
          class="h-full"
          @query="runQuery"
        />
      </aside>
    </div>

    <!-- Document Reader modal -->
    <DocumentReader
      :show="showReader"
      :docs="projectFiles"
      :manual-chunks="manualChunks"
      :target="readerTarget"
      :pdf-url="pdfUrl"
      :page-image-url="pageImageUrl"
      :lang="lang"
      :fetch-pdf-info="fetchPdfInfo"
      :analyze-selection="analyzeSelection"
      :create-manual-chunk="handleCreateManualChunk"
      :delete-manual-chunk="handleDeleteManualChunk"
      @close="showReader = false"
    />

    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="deleteConfirmOpen"
          class="fixed inset-0 z-[80] flex items-center justify-center px-5"
        >
          <div class="absolute inset-0 bg-black/35 backdrop-blur-[2px]" @click="closeDeleteConfirm" />
          <div class="relative w-[min(420px,92vw)] rounded-2xl border bg-white shadow-2xl" style="border-color:#D7DEE8">
            <div class="px-5 pt-5 pb-3">
              <div class="mb-3 flex h-10 w-10 items-center justify-center rounded-xl" style="background:#FEF2F2;border:1px solid #FECACA;color:#B91C1C">
                <svg width="18" height="18" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M6 2h4M2.5 4h11M5 4v9M8 4v9M11 4v9M4 4l.5 10h7L12 4"/>
                </svg>
              </div>
              <h3 class="text-[16px] font-semibold" style="color:#172033">
                {{ deleteConfirmTitle }}
              </h3>
              <p class="mt-2 text-[13px] leading-relaxed" style="color:#667085">
                {{ deleteConfirmMessage }}
              </p>
              <div v-if="pendingDeleteFile" class="mt-3 rounded-lg border px-3 py-2 text-[12px] font-medium truncate" style="border-color:#D7DEE8;background:#F8FAFC;color:#41546F">
                {{ pendingDeleteFile }}
              </div>
            </div>
            <div class="flex justify-end gap-2 border-t px-5 py-3" style="border-color:#E5EAF1">
              <button
                class="rounded-lg border px-4 py-2 text-[13px] font-medium transition-colors"
                style="border-color:#D7DEE8;color:#41546F;background:#FFFFFF"
                @click="closeDeleteConfirm"
              >
                {{ lang === 'zh' ? '取消' : 'Cancel' }}
              </button>
              <button
                class="rounded-lg px-4 py-2 text-[13px] font-semibold text-white transition-colors"
                style="background:#B91C1C"
                @click="confirmDeleteAction"
              >
                {{ lang === 'zh' ? '確認刪除' : 'Delete' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import VisualizationPanel from './components/VisualizationPanel/VisualizationPanel.vue'
import UploadPanel from './components/UploadPanel/UploadPanel.vue'
import ChatPanel from './components/ChatPanel/ChatPanel.vue'
import DocumentReader from './components/DocumentReader/DocumentReader.vue'
import NodeReviewPanel from './components/NodeReviewPanel/NodeReviewPanel.vue'
import ProjectPanel from './components/ProjectPanel/ProjectPanel.vue'
import { useRag } from './composables/useRag'
import type { DocMetadata, IngestPreviewResponse, ManualChunkRequest, ManualChunkInfo, ChunkRelation } from './types/rag'

const {
  ingesting, querying, loadingUmap, loadingGraphAnalysis,
  ingestResult, ingestPreview, queryResult, umapResult, graphAnalysisResult,
  projectFiles, manualChunks, error, projectFilterOptions,
  projects, activeProjectId, activeProject,
  createProject, fetchProjectFilterOptions, fetchExternalVisionPreview, switchProject, deleteProject,
  ingestPdf, commitIngestPreview, discardIngestPreview, removeProjectFile, clearProject,
  pdfUrl, pageImageUrl, analyzeSelection, createManualChunk, deleteManualChunk, fetchManualChunks,
  relations, fetchRelations, createRelation, updateRelationWeight, deleteRelation,
  fetchProjectFiles, fetchPdfInfo, query, fetchUmap, fetchGraphAnalysis,
} = useRag()

const lang = ref<'en' | 'zh'>('zh')
const railOpen = ref(true)
const chatOpen = ref(true)
const showReader = ref(false)
const readerTarget = ref<{ sourceDoc: string; page: number; nonce: number } | null>(null)
const reviewPanelOpen = ref(false)
const deleteConfirmOpen = ref(false)
const pendingDeleteFile = ref<string | null>(null)
const pendingClearAll = ref(false)

const uploadError = computed(() => (ingesting.value ? null : error.value))
const queryError  = computed(() => (querying.value  ? null : error.value))
const totalAutoChunks = computed(() => projectFiles.value.reduce((s, f) => s + f.chunk_count, 0))
const hasContent = computed(() => totalAutoChunks.value > 0 || manualChunks.value.length > 0)
const deleteConfirmTitle = computed(() => {
  if (pendingClearAll.value) return lang.value === 'zh' ? '清除目前專案資料？' : 'Clear this project?'
  return lang.value === 'zh' ? '刪除這份 PDF？' : 'Delete this PDF?'
})
const deleteConfirmMessage = computed(() => {
  if (pendingClearAll.value) {
    return lang.value === 'zh'
      ? '這會移除目前專案中的 PDF、知識節點、節點關係、向量索引與知識圖譜 JSON。此操作無法復原。'
      : 'This removes PDFs, knowledge nodes, node relations, vector indexes, and knowledge graph JSON for this project. This cannot be undone.'
  }
  return lang.value === 'zh'
    ? '這會移除該 PDF 產生的頁面、知識節點、節點關係、向量資料與知識圖譜 JSON。此操作無法復原。'
    : 'This removes pages, knowledge nodes, node relations, vectors, and knowledge graph JSON derived from this PDF. This cannot be undone.'
})
// ── viz cache helpers ─────────────────────────────────────────────────────────

function clearVizCache() {
  umapResult.value = null
  graphAnalysisResult.value = null
}

// Wrappers that invalidate cached visualizations when editable graph data changes
async function handleCreateManualChunk(req: ManualChunkRequest): Promise<ManualChunkInfo> {
  const result = await createManualChunk(req)
  clearVizCache()
  fetchProjectFiles()  // update per-file chunk count in sidebar
  return result
}

async function handleDeleteManualChunk(chunkId: string): Promise<void> {
  await deleteManualChunk(chunkId)
  clearVizCache()
  fetchProjectFiles()
}

async function handleCreateRelation(fromId: string, toId: string, label: string, weight = 1): Promise<ChunkRelation> {
  const result = await createRelation(fromId, toId, label, weight)
  clearVizCache()
  return result
}

async function handleUpdateRelationWeight(relationId: string, weight: number): Promise<ChunkRelation> {
  const result = await updateRelationWeight(relationId, weight)
  clearVizCache()
  return result
}

async function handleDeleteRelation(relationId: string): Promise<void> {
  await deleteRelation(relationId)
  clearVizCache()
}

// Fix signature mismatch: VisualizationPanel emits (question?, threshold?)
// but useRag.fetchGraphAnalysis takes (question?, topK, threshold)
function handleFetchGraphAnalysis(question?: string, threshold?: number): void {
  fetchGraphAnalysis(question, 5, threshold ?? 0.5)
}

function openReaderAtSource(target: { sourceDoc: string; page: number }): void {
  readerTarget.value = { ...target, nonce: Date.now() }
  showReader.value = true
}

watch(activeProjectId, async (id) => {
  if (id) await Promise.all([fetchProjectFiles(), fetchManualChunks(), fetchRelations()])
})

function onCreateProject(name: string, meta: DocMetadata) { createProject(name, meta) }
function onSwitchProject(id: string) {
  if (id === activeProjectId.value) return
  switchProject(id)
}
function onDeleteProject(id: string) { deleteProject(id) }

function requestRemoveProjectFile(filename: string) {
  pendingDeleteFile.value = filename
  pendingClearAll.value = false
  deleteConfirmOpen.value = true
}

function requestClearProject() {
  pendingDeleteFile.value = null
  pendingClearAll.value = true
  deleteConfirmOpen.value = true
}

function closeDeleteConfirm() {
  deleteConfirmOpen.value = false
  pendingDeleteFile.value = null
  pendingClearAll.value = false
}

async function confirmDeleteAction() {
  const filename = pendingDeleteFile.value
  const clearAll = pendingClearAll.value
  closeDeleteConfirm()
  if (clearAll) {
    await clearProject()
    showReader.value = false
    return
  }
  if (filename) {
    await removeProjectFile(filename)
    showReader.value = false
  }
}

async function handleUpload(file: File, loaderType: string, strategy: 'auto' | 'manual') {
  await ingestPdf(file, loaderType, strategy)
  await Promise.all([fetchManualChunks(), fetchRelations()])
  reviewPanelOpen.value = Boolean(ingestPreview.value)
  clearVizCache()
}

async function handleCommitIngestPreview(preview: IngestPreviewResponse) {
  await commitIngestPreview(preview)
  reviewPanelOpen.value = false
  clearVizCache()
}

function handleDiscardIngestPreview() {
  discardIngestPreview()
  reviewPanelOpen.value = false
}

async function runQuery(question: string) {
  await query(question)
  if (umapResult.value) fetchUmap(question)
  if (graphAnalysisResult.value) fetchGraphAnalysis(question, 5)
}

onMounted(async () => {
  await fetchProjectFilterOptions()
  if (activeProjectId.value) {
    await Promise.all([fetchProjectFiles(), fetchManualChunks(), fetchRelations()])
  }
})
</script>
