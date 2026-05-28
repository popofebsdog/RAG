<template>
  <div class="w-full h-full relative overflow-hidden">
    <!-- Tab content (full bleed) -->
    <GraphAnalysisView
      :key="`graph-analysis-${projectId ?? 'none'}`"
      v-show="activeTab === 'graph-analysis'"
      :data="graphAnalysisResult"
      :query-result="queryResult"
      :loading="loadingGraphAnalysis"
      :manual-chunks="manualChunks"
      :relations="relations"
      :project-id="projectId"
      :project-name="projectName"
      :lang="lang"
      :threshold="threshold"
      :active="activeTab === 'graph-analysis'"
      :create-relation="createRelation"
      :update-relation-weight="updateRelationWeight"
      :delete-relation="deleteRelation"
      class="w-full h-full"
      @refresh="onRefresh"
      @threshold-change="onThresholdChange"
    />
    <KnowledgeGraphView
      :key="`knowledge-graph-${projectId ?? 'none'}`"
      v-show="activeTab === 'knowledge-graph'"
      :data="graphAnalysisResult"
      :query-result="queryResult"
      :loading="loadingGraphAnalysis"
      :lang="lang"
      :threshold="threshold"
      :active="activeTab === 'knowledge-graph'"
      :pdf-url="pdfUrl"
      :page-image-url="pageImageUrl"
      class="w-full h-full"
      @refresh="onKgRefresh"
      @view-source="emit('viewSource', $event)"
    />
    <GraphJsonExplorer
      :key="`graph-json-${projectId ?? 'none'}`"
      v-show="activeTab === 'graph-json'"
      :project-id="projectId"
      :lang="lang"
      :active="activeTab === 'graph-json'"
      class="w-full h-full"
    />
    <!-- Floating centered pill tab bar -->
    <div class="absolute top-4 left-1/2 -translate-x-1/2 z-20 pointer-events-none">
      <div class="pointer-events-auto flex items-center gap-0.5 rounded-xl p-1 shadow-sm border" style="background:rgba(253,252,249,0.92);border-color:#E0DBD2">
        <button
          v-for="tab in TABS"
          :key="tab.id"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-all duration-150 hover:bg-black/[0.06]"
          :style="activeTab === tab.id
            ? { background: '#2C2926', color: '#fff' }
            : { color: '#6B6660' }"
          @click="activeTab = tab.id"
        >
          <component :is="tab.icon" class="w-3 h-3 shrink-0" />
          <span>{{ lang === 'zh' ? tab.labelZh : tab.label }}</span>
        </button>

        <!-- Refresh -->
        <button
          v-if="hasContent && activeTab !== 'graph-json'"
          class="ml-1 flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] transition-colors hover:bg-black/[0.06]"
          style="color:#A9A39A"
          :disabled="isLoading"
          @click="onRefresh"
        >
          <span :class="isLoading ? 'animate-spin inline-block' : ''">↻</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, h } from 'vue'
import KnowledgeGraphView from '../KnowledgeGraphView/KnowledgeGraphView.vue'
import GraphAnalysisView from '../GraphAnalysisView/GraphAnalysisView.vue'
import GraphJsonExplorer from '../GraphJsonExplorer/GraphJsonExplorer.vue'
import type {
  GraphAnalysisResponse,
  QueryResponse,
  VisualizationTab,
  ManualChunkInfo,
  ChunkRelation,
} from '../../types/rag'

// Inline SVG icon components
const IconGraph = { render: () => h('svg', { viewBox: '0 0 16 16', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.5', 'stroke-linecap': 'round' }, [h('circle', { cx: '4', cy: '8', r: '2' }), h('circle', { cx: '12', cy: '4', r: '2' }), h('circle', { cx: '12', cy: '12', r: '2' }), h('path', { d: 'M6 8l4-2.5M6 8l4 2.5' })]) }
const IconAnalysis = { render: () => h('svg', { viewBox: '0 0 16 16', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.5', 'stroke-linecap': 'round' }, [h('rect', { x: '2', y: '10', width: '2', height: '4' }), h('rect', { x: '6', y: '6', width: '2', height: '8' }), h('rect', { x: '10', y: '8', width: '2', height: '6' }), h('path', { d: 'M2 2l3 3 3-2 4 4' })]) }
const IconJson = { render: () => h('svg', { viewBox: '0 0 16 16', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.5', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [h('path', { d: 'M5 2H3.8A1.8 1.8 0 0 0 2 3.8v8.4A1.8 1.8 0 0 0 3.8 14H5' }), h('path', { d: 'M11 2h1.2A1.8 1.8 0 0 1 14 3.8v8.4a1.8 1.8 0 0 1-1.8 1.8H11' }), h('path', { d: 'M6.5 6L5 8l1.5 2M9.5 6L11 8l-1.5 2' })]) }

const props = defineProps<{
  hasContent: boolean
  graphAnalysisResult: GraphAnalysisResponse | null
  queryResult: QueryResponse | null
  manualChunks: ManualChunkInfo[]
  relations: ChunkRelation[]
  projectId: string | null
  projectName: string
  loadingGraphAnalysis: boolean
  lang: 'en' | 'zh'
  pdfUrl: (filename: string) => string
  pageImageUrl: (filename: string, pageNum: number) => string
  createRelation: (fromId: string, toId: string, label: string, weight?: number) => Promise<ChunkRelation>
  updateRelationWeight: (id: string, weight: number) => Promise<ChunkRelation>
  deleteRelation: (id: string) => Promise<void>
}>()

const emit = defineEmits<{
  fetchGraphAnalysis: [question?: string, threshold?: number]
  viewSource: [target: { sourceDoc: string; page: number }]
}>()

const TABS: { id: VisualizationTab; label: string; labelZh: string; icon: object }[] = [
  { id: 'graph-analysis',  label: 'Knowledge Graph Edit', labelZh: '知識圖譜編輯', icon: IconAnalysis },
  { id: 'knowledge-graph', label: 'Knowledge Graph', labelZh: '知識圖譜', icon: IconGraph },
  { id: 'graph-json',      label: 'Knowledge Graph JSON', labelZh: '知識圖譜 JSON', icon: IconJson },
]

const activeTab = ref<VisualizationTab>('graph-analysis')
const threshold = ref(0.5)
const lastQuestion = ref<string | undefined>(undefined)

const isLoading = computed(() => props.loadingGraphAnalysis)

watch([activeTab, () => props.hasContent], ([tab, hasContent]) => {
  if (!hasContent) return
  if ((tab === 'knowledge-graph' || tab === 'graph-analysis') && !props.graphAnalysisResult) {
    emit('fetchGraphAnalysis', lastQuestion.value)
  }
}, { immediate: true })

watch(() => props.projectId, () => {
  lastQuestion.value = undefined
})

// When graph data changes (hasContent flips true, or graphAnalysisResult cleared),
// re-fetch the current graph tab automatically
watch(() => props.graphAnalysisResult, (val) => {
  if (!val && props.hasContent && (activeTab.value === 'knowledge-graph' || activeTab.value === 'graph-analysis')) {
    emit('fetchGraphAnalysis', lastQuestion.value)
  }
})

watch(threshold, (val) => {
  if (activeTab.value === 'knowledge-graph' || activeTab.value === 'graph-analysis') {
    emit('fetchGraphAnalysis', lastQuestion.value, val)
  }
})

function onRefresh() {
  if (activeTab.value === 'knowledge-graph' || activeTab.value === 'graph-analysis') {
    emit('fetchGraphAnalysis', lastQuestion.value, threshold.value)
  }
}

function onThresholdChange(th: number) {
  threshold.value = th
}

function onKgRefresh(th: number) {
  threshold.value = th
}
</script>
