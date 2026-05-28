<template>
  <div class="w-full h-full relative flex overflow-hidden">
    <aside class="w-[320px] shrink-0 border-r flex flex-col overflow-hidden" style="border-color:#D7DEE8;background:#F8FAFC">
      <div class="flex-1 overflow-y-auto p-3 space-y-4">

        <section>
          <div class="flex items-center justify-between">
            <p class="section-label mb-0">{{ lang === 'zh' ? '異常警示' : 'Anomaly Alerts' }}</p>
            <span class="text-[12px] tabular-nums" :style="{ color: anomalyItems.length ? '#B91C1C' : '#667085' }">
              {{ anomalyItems.length }}
            </span>
          </div>
          <div v-if="anomalyItems.length" class="mt-2 space-y-2">
            <div
              v-for="(item, index) in anomalyItems"
              :key="`${item.type}-${index}`"
              class="alert-card"
            >
              <div class="flex items-start gap-2">
                <span class="alert-dot" />
                <div class="min-w-0">
                  <p class="text-[13px] font-semibold truncate" style="color:#991B1B">{{ anomalyLabel(item.type) }}</p>
                  <p class="mt-1 text-[12px] leading-relaxed" style="color:#B91C1C">{{ item.message }}</p>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="empty-box mt-2">
            {{ queryResult ? (lang === 'zh' ? '本次查詢未觸發異常' : 'No anomaly in the latest query') : (lang === 'zh' ? '查詢後會顯示異常結果' : 'Run a query to show anomaly results') }}
          </div>
        </section>

        <section>
          <p class="section-label">{{ lang === 'zh' ? '選取知識節點' : 'Selected Knowledge Node' }}</p>
          <div v-if="selected" class="rounded-lg border p-3 space-y-2" style="border-color:#D7DEE8;background:#FFFFFF">
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <p class="text-[14px] font-semibold truncate" style="color:#172033">{{ nodeTitle(selected.id) }}</p>
                <p class="text-[12px] truncate" style="color:#667085">{{ selected.id }}</p>
              </div>
              <span class="node-type">{{ displayNodeType(selected) }}</span>
            </div>
            <div class="flex flex-wrap gap-1.5">
              <span v-if="selected.source_doc" class="meta-chip">{{ selected.source_doc }}</span>
              <span v-if="selected.page > 0" class="meta-chip">p{{ selected.page }}</span>
              <span v-for="tag in selected.hazard_tags" :key="tag" class="hazard-chip">{{ tag }}</span>
            </div>
            <p class="line-clamp-3 text-[13px] leading-relaxed" style="color:#41546F">{{ selected.text }}</p>
            <div class="grid grid-cols-2 gap-2">
              <button class="action-button" @click="fromId = selected.id">{{ lang === 'zh' ? '設為起點知識節點' : 'Set source' }}</button>
              <button class="action-button" @click="toId = selected.id">{{ lang === 'zh' ? '設為終點知識節點' : 'Set target' }}</button>
            </div>
          </div>
          <div v-else class="empty-box">
            {{ lang === 'zh' ? '尚未選取知識節點' : 'No knowledge node selected' }}
          </div>
        </section>

        <section>
          <p class="section-label">{{ lang === 'zh' ? '建立節點關係' : 'Create Node Relation' }}</p>
          <div class="rounded-lg border p-3 space-y-3" style="border-color:#D7DEE8;background:#FFFFFF">
            <div class="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
              <EndpointBox :label="lang === 'zh' ? '起點知識節點' : 'Source node'" :value="fromId ? nodeTitle(fromId) : '-'" />
              <span style="color:#667085">→</span>
              <EndpointBox :label="lang === 'zh' ? '終點知識節點' : 'Target node'" :value="toId ? nodeTitle(toId) : '-'" />
            </div>

            <input
              v-model="relationLabel"
              class="w-full rounded-lg border px-3 py-2 text-[14px] outline-none"
              style="border-color:#D7DEE8;background:#F8FAFC;color:#172033"
              :placeholder="lang === 'zh' ? '節點關係標籤，例如：導致、支援、矛盾' : 'Node relation label, e.g. causes, supports, contradicts'"
            />
            <label class="flex items-center gap-3 text-[12px]" style="color:#667085">
              <span class="shrink-0">{{ lang === 'zh' ? '權重' : 'Weight' }}</span>
              <input v-model.number="relationWeight" class="relation-range flex-1" type="range" min="0" max="1" step="0.05" />
              <span class="w-10 text-right tabular-nums" style="color:#172033">{{ relationWeight.toFixed(2) }}</span>
            </label>
            <div v-if="duplicateRelation" class="notice-box">
              {{ lang === 'zh' ? '這組起點、終點與節點關係標籤已存在，請調整方向或標籤。' : 'This source, target, and node relation label already exists.' }}
            </div>
            <div v-if="relationError" class="notice-box">
              {{ relationError }}
            </div>
            <button
              class="primary-button"
              :disabled="!canCreateRelation || submitting"
              @click="submitRelation"
            >
              {{ submitButtonLabel }}
            </button>
          </div>
        </section>

        <section>
          <div class="flex items-center justify-between">
            <p class="section-label mb-0">{{ lang === 'zh' ? '已建立節點關係' : 'Node Relations' }}</p>
            <span class="text-[12px]" style="color:#667085">{{ visibleManualEdges.length }}</span>
          </div>
          <div v-if="visibleManualEdges.length" class="mt-2 space-y-2">
            <div
              v-for="rel in visibleManualEdges"
              :key="rel.id"
              class="rounded-lg border p-2.5"
              style="border-color:#D7DEE8;background:#FFFFFF"
            >
              <div class="flex items-start gap-2">
                <div class="min-w-0 flex-1">
                  <p class="text-[13px] font-semibold truncate" style="color:#172033">{{ rel.label }}</p>
                  <p class="text-[12px] truncate" style="color:#667085">{{ nodeTitle(rel.from_chunk_id) }} → {{ nodeTitle(rel.to_chunk_id) }}</p>
                </div>
                <button class="icon-button" :aria-label="lang === 'zh' ? '刪除節點關係' : 'Delete node relation'" @click="removeRelation(rel.id)">x</button>
              </div>
              <label class="mt-2 flex items-center gap-2 text-[12px]" style="color:#667085">
                <span>{{ lang === 'zh' ? '權重' : 'Weight' }}</span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  :value="rel.weight"
                  class="relation-range flex-1"
                  @change="changeRelationWeight(rel.id, Number(($event.target as HTMLInputElement).value))"
                />
                <span class="w-10 text-right tabular-nums" style="color:#172033">{{ rel.weight.toFixed(2) }}</span>
              </label>
            </div>
          </div>
          <div v-else class="empty-box mt-2">{{ lang === 'zh' ? '目前知識節點尚無可編輯節點關係' : 'No node relations for the current knowledge nodes' }}</div>
        </section>

      </div>
    </aside>

    <main class="flex-1 relative">
      <div v-if="!data && !loading" class="absolute inset-0 flex flex-col items-center justify-center gap-3">
        <p class="text-[14px]" style="color:#667085">{{ lang === 'zh' ? '上傳或建立知識節點後會顯示知識圖譜' : 'Knowledge graph appears after knowledge nodes are available' }}</p>
      </div>
      <div v-if="loading" class="absolute inset-0 flex items-center justify-center">
        <div class="text-[14px] animate-pulse" style="color:#41546F">{{ lang === 'zh' ? '正在分析知識圖譜結構' : 'Analyzing knowledge graph structure' }}</div>
      </div>
      <div ref="cyContainer" class="w-full h-full" />
      <div v-if="data" class="graph-legend" aria-label="線條說明">
        <div class="legend-item">
          <span class="legend-line legend-manual" />
          <span>{{ lang === 'zh' ? '節點關係' : 'Node relation' }}</span>
        </div>
        <div class="legend-item">
          <span class="legend-line legend-context" />
          <span>{{ lang === 'zh' ? '同源脈絡' : 'Same-source context' }}</span>
        </div>
        <div class="legend-item">
          <span class="legend-line legend-anomaly" />
          <span>{{ lang === 'zh' ? '異常警示' : 'Anomaly alert' }}</span>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted, nextTick, h } from 'vue'
import cytoscape from 'cytoscape'
import type { ChunkRelation, GraphAnalysisNode, GraphAnalysisResponse, ManualChunkInfo, QueryResponse } from '../../types/rag'

const EndpointBox = {
  props: ['label', 'value'],
  render(this: { label: string; value: string }) {
    return h('div', { class: 'min-w-0 rounded-md border px-2 py-1.5', style: 'border-color:#D7DEE8;background:#F8FAFC' }, [
      h('p', { class: 'text-[11px]', style: 'color:#667085' }, this.label),
      h('p', { class: 'text-[12px] font-semibold truncate', style: 'color:#172033' }, this.value),
    ])
  },
}

const props = defineProps<{
  data: GraphAnalysisResponse | null
  queryResult: QueryResponse | null
  loading: boolean
  manualChunks: ManualChunkInfo[]
  relations: ChunkRelation[]
  projectId: string | null
  projectName: string
  lang: 'en' | 'zh'
  threshold: number
  active: boolean
  createRelation: (fromId: string, toId: string, label: string, weight?: number) => Promise<ChunkRelation>
  updateRelationWeight: (id: string, weight: number) => Promise<ChunkRelation>
  deleteRelation: (id: string) => Promise<void>
}>()

const emit = defineEmits<{
  refresh: []
  thresholdChange: [threshold: number]
}>()

const cyContainer = ref<HTMLElement | null>(null)
const selected = ref<GraphAnalysisNode | null>(null)
const fromId = ref('')
const toId = ref('')
const relationLabel = ref('')
const relationWeight = ref(1)
const submitting = ref(false)
const relationError = ref('')
let cy: cytoscape.Core | null = null

const COMMUNITY_COLORS = [
  '#2D6EA3', '#628A3C', '#C06B3E', '#7A5EA8', '#3D8C83',
  '#9A5B6D', '#5B6F8A', '#B28B2E', '#476E5B', '#A14F42',
]

const displayNodes = computed<GraphAnalysisNode[]>(() => {
  const base = (props.data?.nodes ?? [])
    .filter((node) => node.node_type !== 'relation' && node.is_manual)
    .sort(compareNodeOrder)
  const seen = new Set(base.map((node) => node.id))
  const manualOnly: GraphAnalysisNode[] = props.manualChunks
    .filter((node) => !seen.has(node.chunk_id))
    .map((node) => ({
      id: node.chunk_id,
      label: node.label,
      keywords: node.label,
      page: 0,
      source_doc: node.source_doc,
      node_type: 'manual',
      hazard_tags: [],
      project_id: node.project_id,
      degree_centrality: 0,
      betweenness_centrality: 0,
      community: Math.max(0, props.data?.num_communities ?? 0),
      text: node.text,
      is_retrieved: false,
      is_manual: true,
    }))
  return [...base, ...manualOnly].sort(compareNodeOrder)
})

const nodeMap = computed(() => new Map(displayNodes.value.map((node) => [node.id, node])))
const manualLabelMap = computed(() => new Map(props.manualChunks.map((node) => [node.chunk_id, node.label])))
const graphNodes = computed<GraphAnalysisNode[]>(() => {
  return [...displayNodes.value].sort(compareNodeOrder)
})
const visibleNodeIds = computed(() => new Set(graphNodes.value.map((node) => node.id)))
const visibleManualEdges = computed(() =>
  props.relations.filter((rel) => visibleNodeIds.value.has(rel.from_chunk_id) && visibleNodeIds.value.has(rel.to_chunk_id)),
)
const anomalyItems = computed(() => (props.queryResult?.anomalies ?? []).map(normalizeAnomaly))
const hasOutOfDomainAnomaly = computed(() =>
  (props.queryResult?.anomalies ?? []).some((item) => item.type === 'out_of_domain'),
)
const shouldHighlightRetrieved = computed(() => !hasOutOfDomainAnomaly.value)
const retrievedNodeIds = computed(() => {
  if (!shouldHighlightRetrieved.value) return new Set<string>()
  return new Set((props.queryResult?.retrieved_chunks ?? []).map((chunk) => chunk.chunk_id))
})
const duplicateRelation = computed(() => {
  const label = relationLabel.value.trim().toLocaleLowerCase()
  if (!fromId.value || !toId.value || !label) return null
  return props.relations.find((rel) =>
    visibleNodeIds.value.has(rel.from_chunk_id) &&
    visibleNodeIds.value.has(rel.to_chunk_id) &&
    rel.from_chunk_id === fromId.value &&
    rel.to_chunk_id === toId.value &&
    rel.label.trim().toLocaleLowerCase() === label,
  ) ?? null
})

const canCreateRelation = computed(() =>
  Boolean(fromId.value && toId.value && fromId.value !== toId.value && relationLabel.value.trim() && !duplicateRelation.value),
)
const submitButtonLabel = computed(() => {
  if (submitting.value) return props.lang === 'zh' ? '建立中' : 'Creating'
  if (duplicateRelation.value) return props.lang === 'zh' ? '已存在相同節點關係' : 'Node relation exists'
  return props.lang === 'zh' ? '建立並寫入向量庫' : 'Create and vectorize'
})

watch(() => props.data, async (data) => {
  if (!data) {
    selected.value = null
    fromId.value = ''
    toId.value = ''
    relationLabel.value = ''
    relationError.value = ''
    cy?.destroy()
    cy = null
    return
  }
  if (!cyContainer.value) return
  await nextTick()
  renderGraph()
}, { immediate: true })

watch(() => props.projectId, () => {
  selected.value = null
  fromId.value = ''
  toId.value = ''
  relationLabel.value = ''
  relationError.value = ''
  cy?.destroy()
  cy = null
})

watch(visibleNodeIds, (ids) => {
  if (fromId.value && !ids.has(fromId.value)) fromId.value = ''
  if (toId.value && !ids.has(toId.value)) toId.value = ''
})

watch(() => props.relations, async () => {
  if (!props.data || !cyContainer.value) return
  await nextTick()
  renderGraph()
}, { deep: true })

watch(() => props.manualChunks, async () => {
  if (!props.data || !cyContainer.value) return
  await nextTick()
  renderGraph()
}, { deep: true })

watch(() => props.queryResult, async () => {
  if (!props.data || !cyContainer.value) return
  await nextTick()
  renderGraph()
}, { deep: true })

watch(() => props.active, async (active) => {
  if (!active) return
  await nextTick()
  refitGraph()
})

onUnmounted(() => cy?.destroy())

function nodeTitle(id: string) {
  const node = nodeMap.value.get(id)
  return manualLabelMap.value.get(id) || node?.keywords || node?.label || id
}

function displayNodeType(node: GraphAnalysisNode): string {
  if (node.node_type === 'relation') return props.lang === 'zh' ? '節點關係' : 'Node relation'
  return props.lang === 'zh' ? '知識節點' : 'Knowledge node'
}

function queryNodeLabel(): string {
  const question = props.queryResult?.question?.trim() ?? ''
  if (hasOutOfDomainAnomaly.value) {
    return props.lang === 'zh' ? '主題外問題' : 'Out of domain'
  }
  const prefix = props.lang === 'zh' ? '查詢' : 'Query'
  if (!question) return prefix
  return question.length > 28 ? `${prefix}\n${question.slice(0, 28)}…` : `${prefix}\n${question}`
}

function anomalyLabel(type: string) {
  const zh: Record<string, string> = {
    out_of_domain: '主題外問題',
    insufficient_evidence: '缺少明確佐證',
    relation_contradiction: '因果矛盾',
  }
  const en: Record<string, string> = {
    out_of_domain: 'Out-of-domain',
    insufficient_evidence: 'Insufficient evidence',
    relation_contradiction: 'Causal contradiction',
  }
  return props.lang === 'zh' ? (zh[type] ?? type) : (en[type] ?? type.split('_').join(' '))
}

function normalizeAnomaly(item: QueryResponse['anomalies'][number]) {
  if (item.message.includes('關鍵詞重疊') || item.message.includes('災害圖譜關鍵對應')) {
    return {
      ...item,
      type: 'insufficient_evidence',
      message: props.lang === 'zh'
        ? '查詢缺少災害知識圖譜中的明確對應證據'
        : 'The query lacks clear supporting evidence in the disaster knowledge graph',
    }
  }
  if (item.message.includes('最高相似度') || item.message.includes('知識庫差異過大')) {
    return {
      ...item,
      type: 'out_of_domain',
      message: props.lang === 'zh'
        ? '查詢語意與目前知識庫主題不相符'
        : 'The query is outside the current knowledge base topic',
    }
  }
  return item
}

function refitGraph() {
  if (!cy) return
  cy.resize()
  cy.fit(undefined, 90)
  cy.center()
}

function edgeKey(a: string, b: string): string {
  return a < b ? `${a}::${b}` : `${b}::${a}`
}

function buildContextEdges(
  nodes: GraphAnalysisNode[],
  relations: ChunkRelation[],
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
  return (a.keywords || a.label || a.id).localeCompare(b.keywords || b.label || b.id)
}

function deterministicPositions(
  nodes: GraphAnalysisNode[],
  relations: ChunkRelation[],
  includeQuery: boolean,
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
      nodeTitle(a.from_chunk_id).localeCompare(nodeTitle(b.from_chunk_id))
      || nodeTitle(a.to_chunk_id).localeCompare(nodeTitle(b.to_chunk_id))
      || a.label.localeCompare(b.label)
      || a.id.localeCompare(b.id),
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
    for (const target of [...(outgoing.get(id) ?? [])].sort((a, b) => nodeTitle(a).localeCompare(nodeTitle(b)))) {
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

  if (includeQuery) {
    const lastLevel = Math.max(0, ...levels)
    positions.set('__query__', { x: (lastLevel + 1) * xGap, y: 0 })
  }
  return positions
}

async function submitRelation() {
  if (!canCreateRelation.value || submitting.value) return
  relationError.value = ''
  submitting.value = true
  try {
    await props.createRelation(fromId.value, toId.value, relationLabel.value.trim(), relationWeight.value)
    relationLabel.value = ''
    relationWeight.value = 1
    emit('refresh')
  } catch {
    relationError.value = props.lang === 'zh'
      ? '節點關係建立失敗，可能已存在相同節點關係。'
      : 'Could not create node relation. It may already exist.'
  } finally {
    submitting.value = false
  }
}

async function changeRelationWeight(id: string, weight: number) {
  await props.updateRelationWeight(id, weight)
  emit('refresh')
}

async function removeRelation(id: string) {
  await props.deleteRelation(id)
  emit('refresh')
}

function renderGraph() {
  cy?.destroy()

  const sortedNodes = [...graphNodes.value].sort(compareNodeOrder)
  const nodePositions = deterministicPositions(sortedNodes, visibleManualEdges.value, Boolean(props.queryResult))
  const elements: cytoscape.ElementDefinition[] = sortedNodes.map((node) => {
    const color = node.is_manual
      ? '#f59e0b'
      : node.node_type === 'relation'
        ? '#1E4E8C'
        : COMMUNITY_COLORS[node.community % COMMUNITY_COLORS.length]
    const relationCount = visibleManualEdges.value.filter(
      (rel) => rel.from_chunk_id === node.id || rel.to_chunk_id === node.id,
    ).length

    return {
      group: 'nodes' as const,
      position: nodePositions.get(node.id),
      data: {
        id: node.id,
        label: nodeTitle(node.id),
        color,
        size: node.is_manual ? 58 + Math.min(relationCount, 4) * 8 : 32 + node.degree_centrality * 70,
        isRetrieved: shouldHighlightRetrieved.value && node.is_retrieved,
        isManual: node.is_manual,
        nodeType: node.node_type,
      },
    }
  })

  const nodeIds = new Set(sortedNodes.map((node) => node.id))
  const connectedPairs = new Set<string>()

  const orderedRelations = [...visibleManualEdges.value].sort((a, b) =>
    nodeTitle(a.from_chunk_id).localeCompare(nodeTitle(b.from_chunk_id))
    || nodeTitle(a.to_chunk_id).localeCompare(nodeTitle(b.to_chunk_id))
    || a.label.localeCompare(b.label)
    || a.id.localeCompare(b.id),
  )

  orderedRelations.forEach((rel) => {
    if (!nodeIds.has(rel.from_chunk_id) || !nodeIds.has(rel.to_chunk_id)) return
    connectedPairs.add(edgeKey(rel.from_chunk_id, rel.to_chunk_id))
    elements.push({
      group: 'edges' as const,
      data: {
        id: `manual-${rel.id}`,
        source: rel.from_chunk_id,
        target: rel.to_chunk_id,
        weight: rel.weight,
        label: rel.label,
        edgeType: 'manual',
      },
    })
  })

  buildContextEdges(sortedNodes, visibleManualEdges.value, connectedPairs).forEach((edge) => {
    elements.push({
      group: 'edges' as const,
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        weight: 0.55,
        label: props.lang === 'zh' ? '同源脈絡' : 'same source',
        edgeType: 'context',
      },
    })
  })

  if (props.queryResult) {
    const queryIsWarning = hasOutOfDomainAnomaly.value
    elements.push({
      group: 'nodes' as const,
      position: nodePositions.get('__query__'),
      data: {
        id: '__query__',
        label: queryNodeLabel(),
        color: queryIsWarning ? '#DC2626' : '#1E4E8C',
        size: queryIsWarning ? 52 : 50,
        isRetrieved: false,
        isManual: false,
        nodeType: queryIsWarning ? 'query-warning' : 'query',
      },
    })
    const linkedIds = queryIsWarning
      ? []
      : [...retrievedNodeIds.value].filter((id) => nodeIds.has(id)).slice(0, 6)
    linkedIds.forEach((id) => {
      elements.push({
        group: 'edges' as const,
        data: {
          id: `query-${id}`,
          source: '__query__',
          target: id,
          weight: 1,
          label: props.lang === 'zh' ? '命中' : 'match',
          edgeType: 'query',
        },
      })
    })
  }

  cy = cytoscape({
    container: cyContainer.value!,
    elements,
    style: [
      {
        selector: 'node',
        style: {
          'background-color': 'data(color)',
          'background-opacity': 0.22,
          'border-color': 'data(color)',
          'border-width': 2,
          width: 'data(size)',
          height: 'data(size)',
          label: 'data(label)',
          'font-size': 12,
          color: '#41546F',
          'text-valign': 'center',
          'text-halign': 'center',
          'text-wrap': 'wrap',
          'text-max-width': '116px',
          'line-height': 1.18,
        },
      },
      {
        selector: 'node[?isManual]',
        style: {
          'border-width': 3,
          color: '#92400E',
          'font-weight': 'bold',
          'font-size': 13,
        },
      },
      {
        selector: 'node[nodeType = "relation"]',
        style: {
          shape: 'diamond',
          'font-weight': 'bold',
          color: '#1E4E8C',
        },
      },
      {
        selector: 'node[nodeType = "query"]',
        style: {
          shape: 'round-rectangle',
          'background-opacity': 0.22,
          'border-width': 3,
          'border-style': 'dashed',
          color: '#1E4E8C',
          'font-weight': 'bold',
          'font-size': 11,
          'text-max-width': '130px',
        },
      },
      {
        selector: 'node[nodeType = "query-warning"]',
        style: {
          shape: 'hexagon',
          'background-opacity': 0.34,
          'border-width': 4,
          'border-style': 'double',
          color: '#7C2D12',
          'font-weight': 'bold',
          'font-size': 11,
        },
      },
      {
        selector: 'node[?isRetrieved]',
        style: {
          'border-color': '#17643A',
          'border-width': 4,
          'background-opacity': 0.48,
        },
      },
      {
        selector: 'node:selected',
        style: {
          'border-color': '#172033',
          'border-width': 4,
          'background-opacity': 0.62,
        },
      },
      {
        selector: 'edge[edgeType = "manual"]',
        style: {
          width: (ele: cytoscape.EdgeSingular) => Math.max(1.5, (ele.data('weight') as number) * 4),
          'line-color': '#D97706',
          'target-arrow-color': '#D97706',
          'target-arrow-shape': 'triangle',
          opacity: (ele: cytoscape.EdgeSingular) => 0.35 + (ele.data('weight') as number) * 0.6,
          'curve-style': 'bezier',
          label: 'data(label)',
          'font-size': 9,
          color: '#92400E',
          'text-background-color': '#FFFFFF',
          'text-background-opacity': 0.9,
          'text-background-padding': '2px',
          'text-rotation': 'autorotate',
        },
      },
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
          'font-size': 9,
          color: '#6B6660',
          'text-background-color': '#FFFFFF',
          'text-background-opacity': 0.82,
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
      {
        selector: 'edge[edgeType = "anomaly"]',
        style: {
          width: 2,
          'line-color': '#DC2626',
          'line-style': 'dashed',
          'target-arrow-color': '#DC2626',
          'target-arrow-shape': 'triangle',
          opacity: 0.72,
          'curve-style': 'bezier',
          label: 'data(label)',
          'font-size': 9,
          color: '#7C2D12',
          'text-background-color': '#FFF7ED',
          'text-background-opacity': 0.95,
          'text-background-padding': '2px',
          'text-rotation': 'autorotate',
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
    refitGraph()
  })

  cy.on('tap', 'node', (evt) => {
    const id = String(evt.target.id())
    selected.value = nodeMap.value.get(id) ?? null
  })

  cy.on('tap', (evt) => {
    if (evt.target === cy) selected.value = null
  })
}
</script>

<style scoped>
.section-label {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #667085;
}
.empty-box {
  border: 1px dashed #D7DEE8;
  border-radius: 8px;
  padding: 12px;
  background: #FFFFFF;
  color: #667085;
  font-size: 13px;
  text-align: center;
}
.notice-box {
  border: 1px solid #FED7AA;
  border-radius: 8px;
  background: #FFF7ED;
  color: #9A3412;
}
.alert-card {
  border: 1px solid #FECACA;
  border-radius: 8px;
  background: #FEF2F2;
  color: #B91C1C;
}
.notice-box {
  padding: 8px 10px;
  font-size: 12px;
  line-height: 1.5;
}
.alert-card {
  padding: 10px;
}
.alert-dot {
  width: 8px;
  height: 8px;
  margin-top: 4px;
  border-radius: 999px;
  background: #DC2626;
  flex-shrink: 0;
}
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
.legend-anomaly {
  height: 0;
  border-top: 2px dashed #DC2626;
}
.node-type,
.meta-chip,
.hazard-chip {
  border: 1px solid #D7DEE8;
  border-radius: 6px;
  padding: 1px 6px;
  font-size: 11px;
  line-height: 18px;
  color: #41546F;
  background: #F6F8FB;
}
.node-type {
  text-transform: uppercase;
  font-weight: 700;
}
.hazard-chip {
  border-color: #BAD7C3;
  background: #F1FAF4;
  color: #17643A;
}
.action-button,
.primary-button,
.icon-button {
  border: 1px solid #D7DEE8;
  border-radius: 8px;
  background: #FFFFFF;
  color: #41546F;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}
.action-button {
  padding: 7px 8px;
  font-size: 13px;
}
.action-button:hover,
.icon-button:hover {
  background: #EEF3F8;
  border-color: #9BB7D4;
}
.primary-button {
  width: 100%;
  padding: 9px 10px;
  background: #1E4E8C;
  border-color: #1E4E8C;
  color: white;
  font-size: 14px;
  font-weight: 700;
}
.primary-button:disabled {
  opacity: 0.38;
  cursor: not-allowed;
}
.icon-button {
  width: 24px;
  height: 24px;
  line-height: 20px;
  font-size: 13px;
}
.icon-button:hover {
  border-color: #F4B8A8;
  background: #FFF7F5;
  color: #9A3412;
}
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
