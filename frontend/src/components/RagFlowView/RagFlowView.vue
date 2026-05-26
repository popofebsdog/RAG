<template>
  <div class="w-full h-full relative">
    <div v-if="!hasData" class="absolute inset-0 flex flex-col items-center justify-center gap-3">
      <div class="w-14 h-14 rounded-2xl bg-black/[0.04] border border-border flex items-center justify-center">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#C0BAB0" stroke-width="1.5" stroke-linecap="round">
          <path d="M3 12h4l3-9 4 18 3-9h4"/>
        </svg>
      </div>
      <p class="text-[13px] text-faint">Upload a PDF to see the RAG pipeline</p>
    </div>

    <VueFlow
      v-else
      :nodes="nodes"
      :edges="edges"
      :fit-view-on-init="true"
      :nodes-draggable="false"
      :nodes-connectable="false"
      :zoom-on-scroll="true"
      class="w-full h-full"
    >
      <Background :gap="20" :size="1" pattern-color="#D0CBC0" />
      <Controls />
      <template #node-pipeline="{ data }">
        <PipelineNode :data="data" />
      </template>
    </VueFlow>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { VueFlow, type Node, type Edge } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import PipelineNode from './PipelineNode.vue'
import type { QueryResponse, IngestResponse } from '../../types/rag'

const props = defineProps<{
  ingestResult: IngestResponse | null
  queryResult: QueryResponse | null
}>()

const hasData = computed(() => !!props.ingestResult)

const STEP_COLORS: Record<string, string> = {
  pdf: '#f59e0b',
  chunker: '#8b5cf6',
  embedder: '#6366f1',
  faiss: '#22c55e',
  query: '#3b82f6',
  retriever: '#06b6d4',
  llm: '#ec4899',
  answer: '#10b981',
}

const ICONS: Record<string, string> = {
  pdf: '📄',
  chunker: '✂️',
  embedder: '⚡',
  faiss: '🗄️',
  query: '🔍',
  retriever: '🎯',
  llm: '🤖',
  answer: '💡',
}

const PIPELINE_STEPS = [
  { id: 'pdf', label: 'PDF Document', sublabel: 'Source', type: 'pdf' },
  { id: 'chunker', label: 'Chunker', sublabel: 'Split text', type: 'chunker' },
  { id: 'embedder', label: 'Embedder', sublabel: 'sentence-transformers', type: 'embedder' },
  { id: 'faiss', label: 'FAISS Index', sublabel: 'Vector store', type: 'faiss' },
  { id: 'query', label: 'User Query', sublabel: 'Input question', type: 'query' },
  { id: 'retriever', label: 'Retriever', sublabel: 'Top-K search', type: 'retriever' },
  { id: 'llm', label: 'Claude LLM', sublabel: 'claude-sonnet-4-6', type: 'llm' },
  { id: 'answer', label: 'Answer', sublabel: 'Final response', type: 'answer' },
]

const activeIds = computed<Set<string>>(() => {
  if (!props.queryResult) return new Set(['pdf', 'chunker', 'embedder', 'faiss'])
  return new Set(['pdf', 'chunker', 'embedder', 'faiss', 'query', 'retriever', 'llm', 'answer'])
})

const nodes = computed<Node[]>(() => {
  const result: Node[] = []
  const infoMap: Record<string, string> = {}

  if (props.ingestResult) {
    infoMap.pdf = props.ingestResult.filename
    infoMap.chunker = `${props.ingestResult.total_chunks} chunks`
    infoMap.faiss = `${props.ingestResult.total_chunks} vectors`
  }
  if (props.queryResult) {
    infoMap.query = props.queryResult.question.slice(0, 30) + '…'
    infoMap.retriever = `top ${props.queryResult.retrieved_chunks.length} chunks`
    infoMap.answer = props.queryResult.answer.slice(0, 40) + '…'
  }

  // Main pipeline: horizontal layout
  PIPELINE_STEPS.forEach((step, i) => {
    const col = i <= 3 ? i : i - 4
    const row = i <= 3 ? 0 : 1
    result.push({
      id: step.id,
      type: 'pipeline',
      position: { x: col * 220 + 40, y: row * 200 + 40 },
      data: {
        label: step.label,
        sublabel: infoMap[step.id] ?? step.sublabel,
        type: step.type,
        color: STEP_COLORS[step.type],
        icon: ICONS[step.type],
        active: activeIds.value.has(step.id),
      },
    })
  })

  // Retrieved chunk nodes below retriever
  if (props.queryResult) {
    props.queryResult.retrieved_chunks.slice(0, 5).forEach((chunk, i) => {
      result.push({
        id: `retrieved_${chunk.chunk_id}`,
        type: 'pipeline',
        position: { x: 700 + i * 180 - 360, y: 420 },
        data: {
          label: chunk.chunk_id,
          sublabel: `p${chunk.source_page} · ${(chunk.score * 100).toFixed(0)}%`,
          type: 'chunk',
          color: '#6366f1',
          icon: '📝',
          active: true,
        },
      })
    })
  }

  return result
})

const edges = computed<Edge[]>(() => {
  const active = activeIds.value
  const result: Edge[] = [
    { id: 'e-pdf-chunker', source: 'pdf', target: 'chunker', label: 'extract', animated: active.has('chunker'), style: edgeStyle(active.has('chunker')) },
    { id: 'e-chunker-embed', source: 'chunker', target: 'embedder', label: 'chunks', animated: active.has('embedder'), style: edgeStyle(active.has('embedder')) },
    { id: 'e-embed-faiss', source: 'embedder', target: 'faiss', label: 'vectors', animated: active.has('faiss'), style: edgeStyle(active.has('faiss')) },
    { id: 'e-faiss-retriever', source: 'faiss', target: 'retriever', label: 'search', animated: active.has('retriever'), style: edgeStyle(active.has('retriever')) },
    { id: 'e-query-retriever', source: 'query', target: 'retriever', label: 'embed', animated: active.has('retriever'), style: edgeStyle(active.has('retriever')) },
    { id: 'e-retriever-llm', source: 'retriever', target: 'llm', label: 'context', animated: active.has('llm'), style: edgeStyle(active.has('llm')) },
    { id: 'e-llm-answer', source: 'llm', target: 'answer', label: 'generate', animated: active.has('answer'), style: edgeStyle(active.has('answer')) },
  ]

  if (props.queryResult) {
    props.queryResult.retrieved_chunks.slice(0, 5).forEach((chunk) => {
      result.push({
        id: `e-retriever-${chunk.chunk_id}`,
        source: 'retriever',
        target: `retrieved_${chunk.chunk_id}`,
        animated: true,
        style: { stroke: '#7B97B0', strokeWidth: 1.5 },
      })
      result.push({
        id: `e-${chunk.chunk_id}-llm`,
        source: `retrieved_${chunk.chunk_id}`,
        target: 'llm',
        animated: true,
        style: { stroke: '#7B97B0', strokeWidth: 1.5 },
      })
    })
  }

  return result
})

function edgeStyle(active: boolean) {
  return {
    stroke: active ? '#7B97B0' : '#D0CBC0',
    strokeWidth: active ? 2 : 1,
    opacity: active ? 1 : 0.5,
  }
}
</script>

<style>
.vue-flow { background: transparent !important; }
.vue-flow__edge-label { font-size: 10px !important; fill: #8A847C !important; }
.vue-flow__controls { background: #FDFCF9 !important; border-color: #E0DBD2 !important; border-radius: 8px !important; }
.vue-flow__controls button { background: #FDFCF9 !important; border-color: #E0DBD2 !important; color: #6B6660 !important; }
.vue-flow__controls button:hover { background: #EFECE5 !important; }
</style>
