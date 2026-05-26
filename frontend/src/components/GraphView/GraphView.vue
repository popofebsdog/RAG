<template>
  <div class="relative w-full h-full bg-surface rounded-lg overflow-hidden border border-border">
    <!-- Legend -->
    <div class="absolute top-3 left-3 z-10 flex flex-wrap gap-2">
      <span
        v-for="(color, type) in NODE_COLORS"
        :key="type"
        class="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
        :style="{ background: color + '22', border: `1px solid ${color}`, color }"
      >
        {{ ICONS[type] }} {{ type }}
      </span>
    </div>

    <!-- Empty state -->
    <div
      v-if="!graphData"
      class="absolute inset-0 flex flex-col items-center justify-center text-muted gap-3"
    >
      <div class="text-5xl opacity-30">🕸️</div>
      <p class="text-sm">Upload a PDF to see the RAG pipeline graph</p>
    </div>

    <svg ref="svgRef" class="w-full h-full" />

    <!-- Node detail tooltip -->
    <Transition name="slide-up">
      <div
        v-if="selectedNode"
        class="absolute bottom-4 left-4 right-4 bg-panel border border-border rounded-lg p-4 max-h-48 overflow-y-auto"
      >
        <div class="flex items-center justify-between mb-2">
          <span
            class="text-xs font-semibold px-2 py-0.5 rounded-full"
            :style="{
              background: nodeColor(selectedNode.type) + '22',
              border: `1px solid ${nodeColor(selectedNode.type)}`,
              color: nodeColor(selectedNode.type),
            }"
          >
            {{ ICONS[selectedNode.type] }} {{ selectedNode.type }}
          </span>
          <button class="text-muted hover:text-white text-sm" @click="selectedNode = null">✕</button>
        </div>
        <p v-if="selectedNode.data?.score" class="text-xs text-warning mb-1">
          Similarity: {{ (selectedNode.data.score as number).toFixed(4) }}
        </p>
        <p v-if="selectedNode.data?.page" class="text-xs text-muted mb-1">
          Page {{ selectedNode.data.page }}
        </p>
        <p v-if="selectedNode.data?.text" class="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap">
          {{ (selectedNode.data.text as string).slice(0, 400) }}{{ (selectedNode.data.text as string).length > 400 ? '…' : '' }}
        </p>
        <p v-if="selectedNode.type === 'answer' && selectedNode.data?.text" class="text-xs text-slate-200 leading-relaxed">
          {{ selectedNode.data.text as string }}
        </p>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted, nextTick } from 'vue'
import type { GraphData, GraphNode } from '../../types/rag'
import { renderGraph } from './use-graph'

const props = defineProps<{ graphData: GraphData | null }>()

const svgRef = ref<SVGSVGElement | null>(null)
const selectedNode = ref<GraphNode | null>(null)

const NODE_COLORS: Record<string, string> = {
  pdf: '#f59e0b',
  chunk: '#6366f1',
  faiss: '#22c55e',
  query: '#3b82f6',
  llm: '#ec4899',
  answer: '#10b981',
}

const ICONS: Record<string, string> = {
  pdf: '📄',
  chunk: '📝',
  faiss: '🗄️',
  query: '🔍',
  llm: '🤖',
  answer: '💡',
}

function nodeColor(type: string): string {
  return NODE_COLORS[type] ?? '#6b7280'
}

let simulation: ReturnType<typeof renderGraph> | null = null

watch(
  () => props.graphData,
  async (data) => {
    if (!data || !svgRef.value) return
    await nextTick()
    simulation?.stop()
    simulation = renderGraph(svgRef.value, data, (node) => {
      selectedNode.value = selectedNode.value?.id === node.id ? null : node
    })
  },
)

onUnmounted(() => {
  simulation?.stop()
})
</script>

<style scoped>
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.2s ease;
}
.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
