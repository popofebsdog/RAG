<template>
  <div class="w-full h-full relative overflow-hidden">
    <div v-if="!data && !loading" class="absolute inset-0 flex flex-col items-center justify-center gap-3">
      <div class="w-14 h-14 rounded-2xl bg-black/[0.04] border border-border flex items-center justify-center">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#C0BAB0" stroke-width="1.5" stroke-linecap="round">
          <circle cx="7" cy="8" r="2.5"/><circle cx="16" cy="6" r="2.5"/><circle cx="17" cy="15" r="2.5"/><circle cx="6" cy="16" r="2.5"/><circle cx="12" cy="11" r="1.5"/>
        </svg>
      </div>
      <p class="text-[13px]" style="color:#A9A39A">Run a query to project embeddings into 2D space</p>
    </div>
    <div v-if="loading" class="absolute inset-0 flex items-center justify-center">
      <div class="text-[13px] animate-pulse" style="color:#6B6660">Computing UMAP projection…</div>
    </div>

    <div v-if="data && hasRelationVectors" class="absolute top-14 right-3 z-10 rounded-lg px-2.5 py-2 border" style="background:rgba(253,252,249,0.92);border-color:#E0DBD2">
      <label class="flex items-center gap-2 text-[11px]" style="color:#6B6660">
        <input v-model="showRelationVectors" type="checkbox" class="accent-[oklch(0.38_0.09_222)]" />
        <span>顯示節點關係向量</span>
      </label>
    </div>

    <!-- Legend -->
    <div v-if="data" class="absolute top-14 left-3 z-10 text-[11px] flex flex-col gap-1 rounded-lg px-2.5 py-2 border" style="background:rgba(253,252,249,0.92);border-color:#E0DBD2">
      <div class="flex items-center gap-1.5">
        <span class="w-2.5 h-2.5 rounded-full bg-accent/50 inline-block" />
        <span style="color:#A9A39A">知識節點</span>
      </div>
      <div class="flex items-center gap-1.5">
        <span class="w-2.5 h-2.5 rounded-full bg-green-500 inline-block" />
        <span style="color:#A9A39A">Retrieved</span>
      </div>
      <div v-if="data.query_x !== null" class="flex items-center gap-1.5">
        <span class="text-amber-500 font-bold text-xs">✦</span>
        <span style="color:#A9A39A">Query</span>
      </div>
      <div v-if="showRelationVectors && hasRelationVectors" class="flex items-center gap-1.5">
        <span class="text-[13px] leading-none" style="color:#1E4E8C">◆</span>
        <span style="color:#A9A39A">節點關係向量</span>
      </div>
    </div>

    <svg ref="svgRef" class="w-full h-full" />

    <!-- Tooltip -->
    <div
      v-if="tooltip"
      class="absolute pointer-events-none rounded-lg px-2.5 py-2 text-[11px] max-w-64 shadow-sm border"
      style="background:rgba(253,252,249,0.97);border-color:#E0DBD2"
      :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
    >
      <div class="font-mono mb-0.5 truncate" style="color:oklch(0.38 0.09 222)">{{ tooltip.label || tooltip.chunk_id }}</div>
      <div class="mb-1" style="color:#A9A39A">
        {{ tooltip.node_type === 'relation' ? '節點關係向量' : `原文頁 ${tooltip.source_page}` }}
        · {{ (tooltip.score * 100).toFixed(1) }}%
      </div>
      <p style="color:#6B6660">{{ tooltip.text.slice(0, 120) }}…</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import * as d3 from 'd3'
import type { UMAPResponse, UMAPPoint } from '../../types/rag'

const props = defineProps<{
  data: UMAPResponse | null
  loading: boolean
}>()

const svgRef = ref<SVGSVGElement | null>(null)
const tooltip = ref<(UMAPPoint & { x: number; y: number }) | null>(null)
const showRelationVectors = ref(false)

const PAGE_COLORS = d3.schemeTableau10
const visiblePoints = computed(() =>
  props.data?.points.filter((point) => showRelationVectors.value || point.node_type !== 'relation') ?? [],
)
const hasRelationVectors = computed(() =>
  Boolean(props.data?.points.some((point) => point.node_type === 'relation')),
)

watch(() => props.data, async (data) => {
  if (!data || !svgRef.value) return
  await nextTick()
  render(data)
})

watch(showRelationVectors, async () => {
  if (!props.data || !svgRef.value) return
  await nextTick()
  render(props.data)
})

function render(data: UMAPResponse) {
  const el = svgRef.value!
  d3.select(el).selectAll('*').remove()

  const W = el.clientWidth || 800
  const H = el.clientHeight || 600
  const margin = { top: 40, right: 40, bottom: 40, left: 40 }
  const w = W - margin.left - margin.right
  const h = H - margin.top - margin.bottom

  const points = visiblePoints.value
  const allX = points.map((p) => p.x)
  const allY = points.map((p) => p.y)
  if (!points.length) return
  if (data.query_x !== null) { allX.push(data.query_x!); allY.push(data.query_y!) }

  const xScale = d3.scaleLinear().domain(d3.extent(allX) as [number, number]).range([0, w]).nice()
  const yScale = d3.scaleLinear().domain(d3.extent(allY) as [number, number]).range([h, 0]).nice()

  const svg = d3.select(el)
  const zoomG = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

  svg.call(
    d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 10])
      .on('zoom', (e: d3.D3ZoomEvent<SVGSVGElement, unknown>) => {
        zoomG.attr('transform', `translate(${margin.left + e.transform.x},${margin.top + e.transform.y}) scale(${e.transform.k})`)
      }),
  )

  // Background grid
  zoomG.append('g').call(
    d3.axisLeft(yScale).tickSize(-w).tickFormat(() => ''),
  ).selectAll('line').attr('stroke', '#D0CBC0').attr('stroke-opacity', 0.5)
  zoomG.append('g').attr('transform', `translate(0,${h})`).call(
    d3.axisBottom(xScale).tickSize(-h).tickFormat(() => ''),
  ).selectAll('line').attr('stroke', '#D0CBC0').attr('stroke-opacity', 0.5)

  // Inactive chunks
  zoomG.selectAll('circle.inactive')
    .data(points.filter((p) => !p.is_retrieved && p.node_type !== 'relation'))
    .join('circle')
    .attr('cx', (d: UMAPPoint) => xScale(d.x))
    .attr('cy', (d: UMAPPoint) => yScale(d.y))
    .attr('r', 5)
    .attr('fill', (d: UMAPPoint) => PAGE_COLORS[(d.source_page - 1) % PAGE_COLORS.length])
    .attr('fill-opacity', 0.4)
    .attr('stroke', 'none')
    .style('cursor', 'pointer')
    .on('mousemove', (event: MouseEvent, d: UMAPPoint) => showTooltip(event, d))
    .on('mouseleave', () => { tooltip.value = null })

  // Retrieved chunks (highlighted)
  zoomG.selectAll('circle.retrieved')
    .data(points.filter((p) => p.is_retrieved && p.node_type !== 'relation'))
    .join('circle')
    .attr('cx', (d: UMAPPoint) => xScale(d.x))
    .attr('cy', (d: UMAPPoint) => yScale(d.y))
    .attr('r', 9)
    .attr('fill', '#22c55e')
    .attr('fill-opacity', 0.7)
    .attr('stroke', '#22c55e')
    .attr('stroke-width', 1.5)
    .style('cursor', 'pointer')
    .on('mousemove', (event: MouseEvent, d: UMAPPoint) => showTooltip(event, d))
    .on('mouseleave', () => { tooltip.value = null })

  // Score labels for retrieved
  zoomG.selectAll('text.score')
    .data(points.filter((p) => p.is_retrieved && p.node_type !== 'relation'))
    .join('text')
    .attr('x', (d: UMAPPoint) => xScale(d.x))
    .attr('y', (d: UMAPPoint) => yScale(d.y) - 13)
    .attr('text-anchor', 'middle')
    .attr('font-size', 9)
    .attr('fill', '#22c55e')
    .text((d: UMAPPoint) => `${(d.score * 100).toFixed(0)}%`)

  // Relation vectors are searchable relation records, hidden by default.
  zoomG.selectAll('path.relation')
    .data(points.filter((p) => p.node_type === 'relation'))
    .join('path')
    .attr('class', 'relation')
    .attr('d', d3.symbol<UMAPPoint>().type(d3.symbolDiamond).size(105))
    .attr('transform', (d: UMAPPoint) => `translate(${xScale(d.x)},${yScale(d.y)})`)
    .attr('fill', '#1E4E8C')
    .attr('fill-opacity', 0.18)
    .attr('stroke', '#1E4E8C')
    .attr('stroke-width', 1.5)
    .style('cursor', 'pointer')
    .on('mousemove', (event: MouseEvent, d: UMAPPoint) => showTooltip(event, d))
    .on('mouseleave', () => { tooltip.value = null })

  // Query point
  if (data.query_x !== null) {
    const qx = xScale(data.query_x!)
    const qy = yScale(data.query_y!)

    zoomG.append('text')
      .attr('x', qx)
      .attr('y', qy)
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('font-size', 18)
      .text('✦')
      .attr('fill', '#f59e0b')

    zoomG.append('text')
      .attr('x', qx)
      .attr('y', qy - 18)
      .attr('text-anchor', 'middle')
      .attr('font-size', 9)
      .attr('fill', '#f59e0b')
      .text(data.query_label ?? 'Query')
  }
}

function showTooltip(event: MouseEvent, d: UMAPPoint) {
  const rect = svgRef.value!.getBoundingClientRect()
  tooltip.value = {
    ...d,
    x: event.clientX - rect.left + 12,
    y: event.clientY - rect.top - 20,
  }
}
</script>
