<template>
  <div class="w-full h-full relative overflow-hidden">
    <!-- Empty state -->
    <div v-if="!data && !loading" class="absolute inset-0 flex flex-col items-center justify-center gap-3">
      <div class="w-14 h-14 rounded-2xl bg-black/[0.04] border border-border flex items-center justify-center">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#C0BAB0" stroke-width="1.5" stroke-linecap="round">
          <circle cx="6" cy="12" r="3"/><circle cx="18" cy="6" r="3"/><circle cx="18" cy="18" r="3"/>
          <path d="M9 12l6-4.5M9 12l6 4.5"/>
        </svg>
      </div>
      <p class="text-[13px]" style="color:#A9A39A">{{ lang === 'zh' ? '查詢後建立知識圖譜' : 'Run a query to build the knowledge graph' }}</p>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="absolute inset-0 flex items-center justify-center">
      <div class="text-[13px] animate-pulse" style="color:#6B6660">{{ lang === 'zh' ? '建立知識圖譜中…' : 'Building knowledge graph…' }}</div>
    </div>

    <div ref="cyContainer" class="w-full h-full" />
    <div v-if="data && !selected" class="graph-legend" aria-label="線條說明">
      <div class="legend-item">
        <span class="legend-line legend-manual" />
        <span>{{ lang === 'zh' ? '節點關係' : 'Node relation' }}</span>
      </div>
      <div class="legend-item">
        <span class="legend-line legend-context" />
        <span>{{ lang === 'zh' ? '同源脈絡' : 'Same-source context' }}</span>
      </div>
    </div>

    <!-- Node detail panel -->
    <Transition name="fade">
      <div
        v-if="selected"
        class="node-detail-panel absolute bottom-4 left-3 right-3 rounded-xl p-3 text-[12px] shadow-sm border"
        style="background:rgba(253,252,249,0.97);border-color:#E0DBD2"
      >
        <div class="grid h-full grid-cols-[minmax(0,0.95fr)_minmax(320px,1.15fr)] gap-3">
          <div class="min-w-0 overflow-y-auto pr-1">
            <div class="flex justify-between items-start mb-1.5">
              <div class="flex min-w-0 items-center gap-2">
                <span
                  class="shrink-0 px-1.5 py-0.5 rounded border text-[10px] uppercase tracking-wide"
                  :style="{
                    borderColor: selected.node_type === 'relation' ? '#1E4E8C' : selected.is_manual ? '#d97706' : '#C7D3E3',
                    color: selected.node_type === 'relation' ? '#1E4E8C' : selected.is_manual ? '#92400e' : '#41546F',
                    background: selected.node_type === 'relation' ? '#EAF1FA' : selected.is_manual ? '#FFF7ED' : '#F6F8FB',
                  }"
                >
                  {{ displayNodeType(selected) }}
                </span>
                <span class="min-w-0 truncate font-semibold text-[13px]" style="color:#2C2926">{{ displayNodeTitle(selected) }}</span>
              </div>
              <button class="transition-colors text-[14px]" style="color:#667085" aria-label="Close node detail" @click="selected = null">x</button>
            </div>
            <div class="flex gap-3 mb-2 flex-wrap" style="color:#667085">
              <span v-if="selected.page > 0">p{{ selected.page }}</span>
              <span v-if="selected.is_retrieved" class="text-green-700">{{ lang === 'zh' ? '已取回' : 'Retrieved' }}</span>
              <span v-if="selected.is_manual" class="text-amber-500">{{ lang === 'zh' ? '知識節點' : 'Knowledge node' }}</span>
            </div>
            <div class="flex flex-wrap gap-1.5 mb-2">
              <span
                v-if="selected.source_doc"
                class="px-1.5 py-0.5 rounded border text-[11px]"
                style="border-color:#D7DEE8;color:#41546F;background:#F6F8FB"
              >
                {{ selected.source_doc }}
              </span>
              <span
                v-for="tag in selected.hazard_tags"
                :key="tag"
                class="px-1.5 py-0.5 rounded border text-[11px]"
                style="border-color:#BAD7C3;color:#17643A;background:#F1FAF4"
              >
                {{ tag }}
              </span>
            </div>
            <p class="leading-relaxed" style="color:#6B6660">{{ cleanDisplayText(selected.text) }}</p>
          </div>

          <div class="pdf-preview overflow-hidden rounded-lg border bg-white" style="border-color:#D7DEE8">
            <div class="flex items-center justify-between border-b px-3 py-2" style="border-color:#D7DEE8">
              <span class="truncate text-[12px] font-medium" style="color:#41546F">
                {{ selected.source_doc || (lang === 'zh' ? '無原文檔案' : 'No source document') }}
              </span>
              <span v-if="selected.page > 0" class="shrink-0 text-[11px]" style="color:#667085">p{{ selected.page }}</span>
            </div>
            <div v-if="selectedPdfAvailable" class="relative h-full min-h-[260px] overflow-auto bg-[#E9E5DC] p-2">
              <div v-if="pdfPreviewLoading" class="absolute inset-0 z-10 flex items-center justify-center bg-white/70 text-[12px]" style="color:#667085">
                {{ lang === 'zh' ? '載入原文頁面中…' : 'Loading source page…' }}
              </div>
              <div v-if="pdfPreviewError" class="absolute inset-0 z-10 flex items-center justify-center px-4 text-center text-[12px] bg-white" style="color:#B91C1C">
                {{ pdfPreviewError }}
              </div>
              <img
                v-if="selected?.source_doc && selected.page > 0"
                :src="props.pageImageUrl(selected.source_doc, selected.page)"
                class="pdf-page-canvas mx-auto block bg-white shadow-sm"
                :alt="`p${selected.page}`"
                @load="pdfPreviewLoading = false"
                @error="onPreviewImageError"
              />
            </div>
            <div v-else class="flex h-full min-h-[260px] items-center justify-center px-4 text-center text-[12px]" style="color:#667085">
              {{ lang === 'zh' ? '這個知識節點沒有可定位的 PDF 頁面' : 'This knowledge node has no PDF source location' }}
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onUnmounted, nextTick } from 'vue'
import cytoscape from 'cytoscape'
import type { GraphAnalysisResponse, GraphAnalysisNode, QueryResponse } from '../../types/rag'

const props = defineProps<{
  data: GraphAnalysisResponse | null
  queryResult: QueryResponse | null
  loading: boolean
  lang?: 'en' | 'zh'
  threshold: number
  active: boolean
  pdfUrl: (filename: string) => string
  pageImageUrl: (filename: string, pageNum: number) => string
}>()

const cyContainer = ref<HTMLElement | null>(null)
const selected = ref<GraphAnalysisNode | null>(null)
const pdfPreviewLoading = ref(false)
const pdfPreviewError = ref('')
let cy: cytoscape.Core | null = null

const selectedPdfAvailable = computed(() => {
  const node = selected.value
  return Boolean(node?.source_doc && node.page && node.page > 0)
})

const shouldHighlightRetrieved = computed(() =>
  !(props.queryResult?.anomalies ?? []).some((item) => item.type === 'out_of_domain'),
)

const selectedPdfTarget = computed(() => {
  const node = selected.value
  if (!node?.source_doc || !node.page || node.page < 1) return ''
  return `${node.source_doc}::${node.page}`
})

const COMMUNITY_COLORS = [
  '#6366f1', '#ec4899', '#22c55e', '#f59e0b', '#06b6d4',
  '#8b5cf6', '#ef4444', '#84cc16', '#f97316', '#14b8a6',
]

watch(() => props.data, async (data) => {
  if (!data) {
    selected.value = null
    cy?.destroy()
    cy = null
    return
  }
  if (!cyContainer.value) return
  await nextTick()
  renderGraph(data)
})

watch(selectedPdfTarget, async () => {
  pdfPreviewError.value = ''
  pdfPreviewLoading.value = selectedPdfAvailable.value
})

watch(() => props.queryResult, async () => {
  if (!props.data || !cyContainer.value) return
  await nextTick()
  renderGraph(props.data)
}, { deep: true })

watch(() => props.active, async (active) => {
  if (!active) return
  await nextTick()
  refitGraph()
})

onUnmounted(() => {
  cy?.destroy()
})

function langText(lang: 'en' | 'zh' | undefined, zh: string, en: string): string {
  return lang === 'en' ? en : zh
}

function cleanDisplayText(text: string): string {
  return String(text || '')
    .replace(/\s*\^p\d+(?:-[\w\u4e00-\u9fff]+-\d+)?/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

function displayNodeLabel(node: GraphAnalysisNode): string {
  return cleanDisplayText(node.keywords || node.label || node.text || node.id) || node.id
}

function displayNodeTitle(node: GraphAnalysisNode): string {
  return displayNodeLabel(node)
}

function displayNodeType(node: GraphAnalysisNode): string {
  if (node.node_type === 'relation') return langText(props.lang, '節點關係', 'Node relation')
  if (node.node_type === 'query') return langText(props.lang, '查詢', 'Query')
  if (node.node_type === 'query-warning') return langText(props.lang, '主題外問題', 'Out of domain')
  return langText(props.lang, '知識節點', 'Knowledge node')
}

function queryNodeLabel(): string {
  const question = props.queryResult?.question?.trim() ?? ''
  if (!shouldHighlightRetrieved.value) return langText(props.lang, '主題外問題', 'Out of domain')
  const prefix = langText(props.lang, '查詢', 'Query')
  if (!question) return prefix
  return question.length > 28 ? `${prefix}\n${question.slice(0, 28)}…` : `${prefix}\n${question}`
}

function refitGraph() {
  if (!cy) return
  cy.resize()
  cy.fit(undefined, 90)
  cy.center()
}

function onPreviewImageError() {
  pdfPreviewLoading.value = false
  pdfPreviewError.value = props.lang === 'zh'
    ? '無法載入這一頁 PDF 原文'
    : 'Could not load this PDF page'
}

function edgeKey(a: string, b: string): string {
  return a < b ? `${a}::${b}` : `${b}::${a}`
}

function buildContextEdges(
  nodes: GraphAnalysisNode[],
  relations: GraphAnalysisResponse['manual_relations'],
  existingPairs: Set<string>,
): { id: string; source: string; target: string }[] {
  if (nodes.length < 2) return []

  const parent = new Map(nodes.map((node) => [node.id, node.id]))
  const find = (id: string): string => {
    const p = parent.get(id) ?? id
    if (p === id) return p
    const root = find(p)
    parent.set(id, root)
    return root
  }
  const union = (a: string, b: string) => {
    const ra = find(a)
    const rb = find(b)
    if (ra !== rb) parent.set(rb, ra)
  }

  const nodeIds = new Set(nodes.map((node) => node.id))
  for (const rel of relations) {
    if (nodeIds.has(rel.from_chunk_id) && nodeIds.has(rel.to_chunk_id)) {
      union(rel.from_chunk_id, rel.to_chunk_id)
    }
  }

  const groups = new Map<string, GraphAnalysisNode[]>()
  for (const node of nodes) {
    const root = find(node.id)
    groups.set(root, [...(groups.get(root) ?? []), node])
  }
  if (groups.size < 2) return []

  const representatives = [...groups.values()]
    .map((group) => [...group].sort(compareNodeOrder)[0])
    .sort(compareNodeOrder)

  const edges: { id: string; source: string; target: string }[] = []
  for (let i = 0; i < representatives.length - 1; i += 1) {
    const source = representatives[i]
    const target = representatives[i + 1]
    const key = edgeKey(source.id, target.id)
    if (existingPairs.has(key)) continue
    existingPairs.add(key)
    edges.push({
      id: `context-${i}-${source.id}-${target.id}`,
      source: source.id,
      target: target.id,
    })
  }
  return edges
}

function compareNodeOrder(a: GraphAnalysisNode, b: GraphAnalysisNode): number {
  const docCompare = (a.source_doc || '').localeCompare(b.source_doc || '')
  if (docCompare !== 0) return docCompare
  const pageCompare = (a.page || 0) - (b.page || 0)
  if (pageCompare !== 0) return pageCompare
  return (a.keywords || a.label).localeCompare(b.keywords || b.label)
}

function deterministicPositions(
  nodes: GraphAnalysisNode[],
  relations: GraphAnalysisResponse['manual_relations'],
): Map<string, { x: number; y: number }> {
  const ids = new Set(nodes.map((node) => node.id))
  const outgoing = new Map<string, string[]>()
  const indegree = new Map<string, number>()
  nodes.forEach((node) => {
    outgoing.set(node.id, [])
    indegree.set(node.id, 0)
  })

  const orderedRelations = [...relations]
    .filter((rel) => ids.has(rel.from_chunk_id) && ids.has(rel.to_chunk_id))
    .sort((a, b) =>
      a.from_chunk_id.localeCompare(b.from_chunk_id)
      || a.to_chunk_id.localeCompare(b.to_chunk_id)
      || a.label.localeCompare(b.label),
    )

  for (const rel of orderedRelations) {
    outgoing.get(rel.from_chunk_id)?.push(rel.to_chunk_id)
    indegree.set(rel.to_chunk_id, (indegree.get(rel.to_chunk_id) ?? 0) + 1)
  }

  const level = new Map<string, number>()
  const queue = nodes
    .filter((node) => (indegree.get(node.id) ?? 0) === 0)
    .sort(compareNodeOrder)
    .map((node) => node.id)
  if (queue.length === 0 && nodes[0]) queue.push(nodes[0].id)
  queue.forEach((id) => level.set(id, 0))

  for (let i = 0; i < queue.length; i += 1) {
    const id = queue[i]
    const nextLevel = (level.get(id) ?? 0) + 1
    for (const target of [...(outgoing.get(id) ?? [])].sort()) {
      if ((level.get(target) ?? -1) < nextLevel) level.set(target, nextLevel)
      indegree.set(target, Math.max(0, (indegree.get(target) ?? 0) - 1))
      if ((indegree.get(target) ?? 0) === 0 && !queue.includes(target)) queue.push(target)
    }
  }

  nodes.forEach((node, index) => {
    if (!level.has(node.id)) level.set(node.id, index)
  })

  const byLevel = new Map<number, GraphAnalysisNode[]>()
  nodes.forEach((node) => {
    const lv = level.get(node.id) ?? 0
    byLevel.set(lv, [...(byLevel.get(lv) ?? []), node])
  })

  const positions = new Map<string, { x: number; y: number }>()
  const xGap = 260
  const yGap = 145
  const levels = [...byLevel.keys()].sort((a, b) => a - b)
  for (const lv of levels) {
    const group = (byLevel.get(lv) ?? []).sort(compareNodeOrder)
    const offset = (group.length - 1) / 2
    group.forEach((node, index) => {
      positions.set(node.id, {
        x: lv * xGap,
        y: (index - offset) * yGap,
      })
    })
  }
  return positions
}

function renderGraph(data: GraphAnalysisResponse) {
  cy?.destroy()

  const elements: cytoscape.ElementDefinition[] = []

  // ── Nodes ────────────────────────────────────────────────────────────────
  const relationNodeIds = new Set<string>()
  for (const rel of data.manual_relations) {
    relationNodeIds.add(rel.from_chunk_id)
    relationNodeIds.add(rel.to_chunk_id)
  }

  const knowledgeNodes = data.nodes
    .filter((node) => node.node_type !== 'relation' && node.is_manual)
    .sort(compareNodeOrder)
  const visibleNodes = knowledgeNodes
  const nodeIds = new Set(visibleNodes.map((node) => node.id))
  const nodesById = new Map(visibleNodes.map((node) => [node.id, node]))
  const connectedPairs = new Set<string>()
  const nodePositions = deterministicPositions(visibleNodes, data.manual_relations)
  const queryPosition = (() => {
    if (!props.queryResult) return null
    const positions = [...nodePositions.values()]
    const maxX = positions.length ? Math.max(...positions.map((p) => p.x)) : 0
    return { x: maxX + 260, y: 0 }
  })()

  for (const node of visibleNodes) {
    const color = node.is_manual
      ? '#f59e0b'
      : COMMUNITY_COLORS[node.community % COMMUNITY_COLORS.length]
    const relationCount = data.manual_relations.filter(
      (rel) => rel.from_chunk_id === node.id || rel.to_chunk_id === node.id,
    ).length
    const size = node.is_manual
      ? 58 + Math.min(relationCount, 4) * 8
      : 32 + node.degree_centrality * 70

    elements.push({
      group: 'nodes',
      position: nodePositions.get(node.id),
      data: {
        id: node.id,
        label: displayNodeLabel(node),
        color,
        size,
        isRetrieved: shouldHighlightRetrieved.value && node.is_retrieved,
        isManual: node.is_manual,
        nodeType: node.node_type,
        sourceDoc: node.source_doc,
        hazardTags: node.hazard_tags.join(', '),
        projectId: node.project_id,
        page: node.page,
        degree_centrality: node.degree_centrality,
        betweenness_centrality: node.betweenness_centrality,
        community: node.community,
        text: node.text,
        keywords: node.keywords,
      },
    })
  }

  // ── VLM/user knowledge relation edges ─────────────────────────────────────
  const visibleRelations = [...data.manual_relations].sort((a, b) => {
    const fromCompare = (nodesById.get(a.from_chunk_id)?.label || a.from_chunk_id)
      .localeCompare(nodesById.get(b.from_chunk_id)?.label || b.from_chunk_id)
    if (fromCompare !== 0) return fromCompare
    const toCompare = (nodesById.get(a.to_chunk_id)?.label || a.to_chunk_id)
      .localeCompare(nodesById.get(b.to_chunk_id)?.label || b.to_chunk_id)
    if (toCompare !== 0) return toCompare
    return a.label.localeCompare(b.label)
  })

  for (const rel of visibleRelations) {
    // Only draw if both endpoints exist in this graph
    if (!nodeIds.has(rel.from_chunk_id) || !nodeIds.has(rel.to_chunk_id)) continue
    connectedPairs.add(edgeKey(rel.from_chunk_id, rel.to_chunk_id))
    elements.push({
      group: 'edges',
      data: {
        id: `manual-${rel.id}`,
        source: rel.from_chunk_id,
        target: rel.to_chunk_id,
        label: rel.label,
        weight: rel.weight,
        edgeType: 'manual',
      },
    })
  }

  const contextEdges = buildContextEdges(visibleNodes, data.manual_relations, connectedPairs)
  for (const edge of contextEdges) {
    const source = nodesById.get(edge.source)
    const target = nodesById.get(edge.target)
    elements.push({
      group: 'edges',
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: source?.source_doc && source.source_doc === target?.source_doc
          ? (langText(props.lang, '同源脈絡', 'same source'))
          : (langText(props.lang, '相關脈絡', 'context')),
        weight: 0.55,
        edgeType: 'context',
      },
    })
  }

  if (props.queryResult && queryPosition) {
    const queryIsWarning = !shouldHighlightRetrieved.value
    elements.push({
      group: 'nodes',
      position: queryPosition,
      data: {
        id: '__query__',
        label: queryNodeLabel(),
        color: queryIsWarning ? '#DC2626' : '#1E4E8C',
        size: queryIsWarning ? 52 : 50,
        isRetrieved: false,
        isManual: false,
        nodeType: queryIsWarning ? 'query-warning' : 'query',
        sourceDoc: '',
        hazardTags: '',
        projectId: '',
        page: 0,
        degree_centrality: 0,
        betweenness_centrality: 0,
        community: 0,
        text: props.queryResult.question,
        keywords: props.queryResult.question,
      },
    })

    if (!queryIsWarning) {
      const retrievedIds = new Set(props.queryResult.retrieved_chunks.map((chunk) => chunk.chunk_id))
      ;[...retrievedIds]
        .filter((id) => nodeIds.has(id))
        .slice(0, 6)
        .forEach((id) => {
          elements.push({
            group: 'edges',
            data: {
              id: `query-${id}`,
              source: '__query__',
              target: id,
              label: langText(props.lang, '命中', 'match'),
              weight: 1,
              edgeType: 'query',
            },
          })
        })
    }
  }

  cy = cytoscape({
    container: cyContainer.value!,
    elements,
    style: [
      // ── base node ──
      {
        selector: 'node',
        style: {
          'background-color': 'data(color)',
          'background-opacity': 0.25,
          'border-color': 'data(color)',
          'border-width': 2,
          width: 'data(size)',
          height: 'data(size)',
          label: 'data(label)',
          'font-size': 13,
          color: '#6B6660',
          'text-valign': 'center',
          'text-halign': 'center',
          'text-wrap': 'wrap',
          'text-max-width': '118px',
          'line-height': 1.18,
          'overlay-padding': 4,
        },
      },
      // ── manual chunk node ──
      {
        selector: 'node[?isManual]',
        style: {
          'background-color': '#f59e0b',
          'background-opacity': 0.2,
          'border-color': '#f59e0b',
          'border-width': 2.5,
          'border-style': 'solid',
          color: '#92400e',
          'font-size': 14,
          'font-weight': 'bold',
        },
      },
      {
        selector: 'node[nodeType = "relation"]',
        style: {
          shape: 'diamond',
          'background-color': '#1E4E8C',
          'background-opacity': 0.18,
          'border-color': '#1E4E8C',
          color: '#1E4E8C',
          'font-weight': 'bold',
        },
      },
      {
        selector: 'node[nodeType = "query"]',
        style: {
          shape: 'round-rectangle',
          'background-color': '#1E4E8C',
          'background-opacity': 0.22,
          'border-color': '#1E4E8C',
          'border-width': 3,
          'border-style': 'dashed',
          color: '#1E4E8C',
          'font-size': 11,
          'font-weight': 'bold',
          'text-max-width': '130px',
        },
      },
      {
        selector: 'node[nodeType = "query-warning"]',
        style: {
          shape: 'hexagon',
          'background-color': '#DC2626',
          'background-opacity': 0.34,
          'border-color': '#DC2626',
          'border-width': 4,
          'border-style': 'double',
          color: '#7C2D12',
          'font-size': 11,
          'font-weight': 'bold',
          'text-max-width': '120px',
        },
      },
      // ── retrieved node ──
      {
        selector: 'node[?isRetrieved]',
        style: {
          'border-width': 3,
          'background-opacity': 0.5,
          'border-color': '#22c55e',
        },
      },
      {
        selector: 'node:selected',
        style: { 'border-width': 3, 'background-opacity': 0.7 },
      },
      // ── VLM/user knowledge relation edges ──
      {
        selector: 'edge[edgeType = "manual"]',
        style: {
          width: (ele: cytoscape.EdgeSingular) =>
            Math.max(2, (ele.data('weight') as number) * 4.5),
          'line-color': '#d97706',
          'target-arrow-color': '#d97706',
          'target-arrow-shape': 'triangle',
          'arrow-scale': 1.2,
          opacity: (ele: cytoscape.EdgeSingular) =>
            0.35 + (ele.data('weight') as number) * 0.6,
          'curve-style': 'bezier',
          label: 'data(label)',
          'font-size': 11,
          color: '#92400e',
          'text-background-color': '#FFFBF5',
          'text-background-opacity': 0.9,
          'text-background-padding': '3px',
          'text-rotation': 'autorotate',
        },
      },
      // ── context bridge edges: visual connectivity, not causal claims ──
      {
        selector: 'edge[edgeType = "context"]',
        style: {
          width: 1.8,
          'line-color': '#A9A39A',
          'line-style': 'dashed',
          'target-arrow-shape': 'none',
          opacity: 0.42,
          'curve-style': 'bezier',
          label: 'data(label)',
          'font-size': 10,
          color: '#6B6660',
          'text-background-color': '#FFFBF5',
          'text-background-opacity': 0.85,
          'text-background-padding': '2px',
        },
      },
      {
        selector: 'edge[edgeType = "query"]',
        style: {
          width: 2,
          'line-color': '#17643A',
          'target-arrow-color': '#17643A',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'line-style': 'dashed',
          label: 'data(label)',
          'font-size': 9,
          color: '#17643A',
          'text-background-color': '#FDFCF9',
          'text-background-opacity': 0.85,
          'text-background-padding': '2px',
        },
      },
    ],
    layout: {
      name: 'preset',
      animate: false,
      fit: true,
      padding: 120,
    } as cytoscape.LayoutOptions,
  })

  cy.ready(() => {
    if (!cy) return
    refitGraph()
    cy.minZoom(0.18)
    cy.maxZoom(2.2)
  })

  cy.on('tap', 'node', (evt) => {
    const d = evt.target.data()
    if (d.id === '__query__') {
      selected.value = null
      return
    }
    selected.value = {
      id: d.id,
      label: d.label,
      keywords: d.keywords ?? '',
      page: d.page,
      source_doc: d.sourceDoc ?? '',
      node_type: d.nodeType ?? 'auto',
      hazard_tags: d.hazardTags ? String(d.hazardTags).split(', ').filter(Boolean) : [],
      project_id: d.projectId ?? 'default',
      degree_centrality: d.degree_centrality,
      betweenness_centrality: d.betweenness_centrality,
      community: d.community,
      text: d.text,
      is_retrieved: d.isRetrieved,
      is_manual: d.isManual ?? false,
    }
  })

  cy.on('tap', (evt) => {
    if (evt.target === cy) selected.value = null
  })
}
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.graph-legend {
  position: absolute;
  left: 50%;
  bottom: 16px;
  z-index: 12;
  display: flex;
  align-items: center;
  gap: 14px;
  max-width: calc(100% - 32px);
  transform: translateX(-50%);
  border: 1px solid #D7DEE8;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 8px 22px rgba(23, 32, 51, 0.08);
  padding: 8px 12px;
  color: #41546F;
  font-size: 12px;
  backdrop-filter: blur(8px);
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  white-space: nowrap;
}
.legend-line {
  width: 34px;
  height: 3px;
  border-radius: 999px;
  flex-shrink: 0;
}
.legend-manual {
  background: #D97706;
}
.legend-context {
  height: 0;
  border-top: 2px dashed #A9A39A;
}
.pdf-page-canvas {
  max-width: 100%;
  height: auto !important;
}
</style>
