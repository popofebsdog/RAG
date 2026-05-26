import * as d3 from 'd3'
import type { GraphData, GraphNode } from '../../types/rag'

const NODE_COLORS: Record<string, string> = {
  pdf: '#f59e0b',
  chunk: '#6366f1',
  embedding: '#8b5cf6',
  faiss: '#22c55e',
  query: '#3b82f6',
  llm: '#ec4899',
  answer: '#10b981',
}

const NODE_RADIUS: Record<string, number> = {
  pdf: 36,
  faiss: 32,
  llm: 32,
  query: 28,
  answer: 28,
  chunk: 20,
  embedding: 16,
}

interface D3Node extends d3.SimulationNodeDatum {
  id: string
  label: string
  type: string
  active: boolean
  data: Record<string, unknown>
}

interface D3Link extends d3.SimulationLinkDatum<D3Node> {
  label: string
  active: boolean
}

export function renderGraph(
  svgEl: SVGSVGElement,
  graphData: GraphData,
  onNodeClick: (node: GraphNode) => void,
) {
  const width = svgEl.clientWidth || 800
  const height = svgEl.clientHeight || 600

  d3.select(svgEl).selectAll('*').remove()

  const svg = d3.select(svgEl).attr('viewBox', `0 0 ${width} ${height}`)

  const defs = svg.append('defs')
  for (const [type, color] of Object.entries(NODE_COLORS)) {
    defs
      .append('marker')
      .attr('id', `arrow-${type}`)
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 28)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', color)
      .attr('opacity', 0.8)
  }
  defs
    .append('marker')
    .attr('id', 'arrow-inactive')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 28)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', '#374151')

  const nodes: D3Node[] = graphData.nodes.map((n) => ({ ...n }))
  const nodeMap = new Map(nodes.map((n) => [n.id, n]))

  const links: D3Link[] = graphData.edges
    .map((e) => ({
      source: nodeMap.get(e.source) ?? e.source,
      target: nodeMap.get(e.target) ?? e.target,
      label: e.label,
      active: e.active,
    }))
    .filter((l) => l.source && l.target)

  const simulation = d3
    .forceSimulation<D3Node>(nodes)
    .force(
      'link',
      d3
        .forceLink<D3Node, D3Link>(links)
        .id((d) => d.id)
        .distance((l: D3Link) => (l.active ? 120 : 80)),
    )
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force(
      'collision',
      d3.forceCollide<D3Node>().radius((d) => (NODE_RADIUS[d.type] ?? 20) + 12),
    )

  const zoomGroup = svg.append('g')

  svg.call(
    d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .on('zoom', (event: d3.D3ZoomEvent<SVGSVGElement, unknown>) => {
        zoomGroup.attr('transform', event.transform.toString())
      }),
  )

  const link = zoomGroup
    .append('g')
    .selectAll<SVGLineElement, D3Link>('line')
    .data(links)
    .join('line')
    .attr('stroke', (d: D3Link) => (d.active ? '#6366f1' : '#2d3148'))
    .attr('stroke-width', (d: D3Link) => (d.active ? 2 : 1))
    .attr('stroke-opacity', (d: D3Link) => (d.active ? 0.9 : 0.3))
    .attr('marker-end', (d: D3Link) => {
      if (!d.active) return 'url(#arrow-inactive)'
      const target = d.target as D3Node
      return `url(#arrow-${target.type})`
    })

  const edgeLabel = zoomGroup
    .append('g')
    .selectAll<SVGTextElement, D3Link>('text')
    .data(links.filter((l) => l.active && l.label))
    .join('text')
    .attr('font-size', 10)
    .attr('fill', '#94a3b8')
    .attr('text-anchor', 'middle')
    .text((d: D3Link) => d.label)

  const node = zoomGroup
    .append('g')
    .selectAll<SVGGElement, D3Node>('g')
    .data(nodes)
    .join('g')
    .attr('cursor', 'pointer')
    .on('click', (_event: MouseEvent, d: D3Node) => onNodeClick(d as unknown as GraphNode))
    .call(
      d3
        .drag<SVGGElement, D3Node>()
        .on('start', (event: d3.D3DragEvent<SVGGElement, D3Node, D3Node>, d: D3Node) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event: d3.D3DragEvent<SVGGElement, D3Node, D3Node>, d: D3Node) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event: d3.D3DragEvent<SVGGElement, D3Node, D3Node>, d: D3Node) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        }),
    )

  node
    .append('circle')
    .attr('r', (d: D3Node) => NODE_RADIUS[d.type] ?? 20)
    .attr('fill', (d: D3Node) =>
      d.active ? (NODE_COLORS[d.type] ?? '#6b7280') + '22' : '#1a1d27',
    )
    .attr('stroke', (d: D3Node) =>
      d.active ? (NODE_COLORS[d.type] ?? '#6b7280') : '#2d3148',
    )
    .attr('stroke-width', (d: D3Node) => (d.active ? 2 : 1))

  node
    .filter((d: D3Node) => d.active)
    .append('circle')
    .attr('r', (d: D3Node) => NODE_RADIUS[d.type] ?? 20)
    .attr('fill', 'none')
    .attr('stroke', (d: D3Node) => NODE_COLORS[d.type] ?? '#6b7280')
    .attr('stroke-width', 1)
    .attr('opacity', 0.4)

  const iconMap: Record<string, string> = {
    pdf: '📄',
    faiss: '🗄️',
    query: '🔍',
    llm: '🤖',
    answer: '💡',
    chunk: '📝',
    embedding: '⚡',
  }

  node
    .append('text')
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'central')
    .attr('y', -4)
    .attr('font-size', (d: D3Node) => `${(NODE_RADIUS[d.type] ?? 20) * 0.7}px`)
    .text((d: D3Node) => iconMap[d.type] ?? '●')

  node
    .append('text')
    .attr('text-anchor', 'middle')
    .attr('y', (d: D3Node) => (NODE_RADIUS[d.type] ?? 20) + 14)
    .attr('font-size', 10)
    .attr('fill', (d: D3Node) => (d.active ? '#e2e8f0' : '#4b5563'))
    .each(function (this: SVGTextElement, d: D3Node) {
      const lines = d.label.split('\n')
      const el = d3.select<SVGTextElement, D3Node>(this)
      lines.forEach((line, i) => {
        el.append('tspan')
          .attr('x', 0)
          .attr('dy', i === 0 ? 0 : 12)
          .text(line)
      })
    })

  simulation.on('tick', () => {
    link
      .attr('x1', (d: D3Link) => (d.source as D3Node).x ?? 0)
      .attr('y1', (d: D3Link) => (d.source as D3Node).y ?? 0)
      .attr('x2', (d: D3Link) => (d.target as D3Node).x ?? 0)
      .attr('y2', (d: D3Link) => (d.target as D3Node).y ?? 0)

    edgeLabel
      .attr(
        'x',
        (d: D3Link) =>
          (((d.source as D3Node).x ?? 0) + ((d.target as D3Node).x ?? 0)) / 2,
      )
      .attr(
        'y',
        (d: D3Link) =>
          (((d.source as D3Node).y ?? 0) + ((d.target as D3Node).y ?? 0)) / 2 - 6,
      )

    node.attr('transform', (d: D3Node) => `translate(${d.x ?? 0},${d.y ?? 0})`)
  })

  return simulation
}
