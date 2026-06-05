import type { ManifestItem, GraphNode, GraphEdge, GraphRelationType, ConceptCluster, ProvenanceLabel } from '@/types'

/**
 * Karpathy LLM-Wiki 三层架构映射：
 *   Layer 0 (Raw)      → source 节点（源文档）
 *   Layer 1 (Wiki)     → concept 节点（编译提取的概念）+ summary 节点
 *   Layer 2 (Schema)   → 类型化语义边（概念间的共现/相似关系）
 *
 * 关键设计：当前端发现后端 concept 节点缺失时（wiki/concepts/ 为空），
 * 自动从 manifests.compiled_summary.concepts 提取并生成概念节点和语义边。
 */

// ── 边类型样式配置 ──────────────────────────────────────
export const EDGE_STYLES: Record<GraphRelationType, { color: string; label: string; dash?: string }> = {
  compiled_to:      { color: '#a39e98', label: '编译为' },
  contains_concept: { color: '#0075de', label: '包含概念' },
  related_to:       { color: '#1aae39', label: '语义关联', dash: '4 3' },
  same_type:        { color: '#dd5b00', label: '同类型', dash: '2 4' },
}

// ── 节点类型样式配置 ──────────────────────────────────────
export const NODE_STYLES: Record<string, { color: string; bg: string; label: string }> = {
  concept:  { color: '#1aae39', bg: 'rgba(26,174,57,0.08)', label: '概念' },
  source:   { color: '#0075de', bg: 'rgba(0,117,222,0.08)', label: '文档' },
  summary:  { color: '#7c3aed', bg: 'rgba(124,58,237,0.08)', label: '摘要' },
}

// ── 溯源标签样式配置 ──────────────────────────────────────
export const PROVENANCE_STYLES: Record<string, { color: string; bg: string; label: string }> = {
  extracted: { color: '#1aae39', bg: 'rgba(26,174,57,0.12)', label: '直接提取' },
  merged:    { color: '#0075de', bg: 'rgba(0,117,222,0.12)', label: '合并重组' },
  inferred:  { color: '#dd8800', bg: 'rgba(221,136,0,0.12)', label: '推断补充' },
  ambiguous: { color: '#d45656', bg: 'rgba(212,86,86,0.12)', label: '来源不明' },
}

// ── 构建概念簇（从 manifests 提取概念并聚合）──────────────
export function buildConceptClusters(manifests: ManifestItem[]): Map<string, ConceptCluster> {
  const clusters = new Map<string, ConceptCluster>()

  for (const m of manifests) {
    if (!m.compiled_summary?.concepts) continue
    for (const raw of m.compiled_summary.concepts) {
      const name = typeof raw === 'string' ? raw : raw.name
      if (!name) continue
      const key = name.toLowerCase().trim()

      if (clusters.has(key)) {
        const c = clusters.get(key)!
        c.sourceCount++
        c.sources.push({ id: m.id, title: m.title })
        if (!c.explanation && typeof raw !== 'string' && raw.explanation) {
          c.explanation = raw.explanation
        }
      } else {
        clusters.set(key, {
          id: `concept:${key.replace(/\s+/g, '-')}`,
          name,
          explanation: typeof raw !== 'string' ? raw.explanation : undefined,
          sourceCount: 1,
          sources: [{ id: m.id, title: m.title }],
        })
      }
    }
  }

  return clusters
}

// ── 从后端图谱 + manifests 构建前端完整的语义图谱 ──────
export interface SemanticGraph {
  nodes: SemanticNode[]
  edges: SemanticEdge[]
  conceptClusters: Map<string, ConceptCluster>
  stats: {
    totalNodes: number
    conceptNodes: number
    sourceNodes: number
    summaryNodes: number
    totalEdges: number
  }
}

export interface SemanticNode extends GraphNode {
  degree: number
  conceptData?: ConceptCluster
  provenance?: ProvenanceLabel
  /** 溯源置信度 0-1 */
  provenanceConfidence?: number
}

export interface SemanticEdge extends GraphEdge {
  id: string
}

export function buildSemanticGraph(
  graphNodes: GraphNode[],
  graphEdges: GraphEdge[],
  manifests: ManifestItem[],
): SemanticGraph {
  const conceptClusters = buildConceptClusters(manifests)
  const nodeMap = new Map<string, GraphNode>()
  const edgeList: SemanticEdge[] = []
  let edgeIdx = 0

  // Add all backend nodes
  for (const n of graphNodes) {
    nodeMap.set(n.id, n)
  }

  // Add all backend edges
  for (const e of graphEdges) {
    edgeList.push({ ...e, id: `edge-${edgeIdx++}` })
  }

  // Check if backend already has concept nodes
  const backendConceptCount = graphNodes.filter(n => n.node_type === 'concept').length

  // If backend has few/no concept nodes, generate them from manifests
  if (backendConceptCount < conceptClusters.size) {
    // Create concept nodes from manifest compiled_summary.concepts
    for (const [, cluster] of conceptClusters) {
      const conceptId = cluster.id
      if (!nodeMap.has(conceptId)) {
        nodeMap.set(conceptId, {
          id: conceptId,
          label: cluster.name,
          node_type: 'concept',
          metadata: { sourceCount: String(cluster.sourceCount) },
        })
      }
    }

    // Create source → concept edges (contains_concept)
    for (const m of manifests) {
      if (!m.compiled_summary?.concepts) continue
      for (const raw of m.compiled_summary.concepts) {
        const name = typeof raw === 'string' ? raw : raw.name
        if (!name) continue
        const conceptId = `concept:${name.toLowerCase().trim().replace(/\s+/g, '-')}`
        if (nodeMap.has(conceptId) && nodeMap.has(m.id)) {
          edgeList.push({
            source: m.id,
            target: conceptId,
            relation: 'contains_concept',
            weight: 1.0,
            id: `edge-${edgeIdx++}`,
          })
        }
      }
    }

    // Create concept → concept co-occurrence edges (related_to)
    // Two concepts are related if they appear in the same document
    const conceptPairs = new Map<string, number>()
    for (const m of manifests) {
      if (!m.compiled_summary?.concepts) continue
      const concepts = m.compiled_summary.concepts
        .map(c => typeof c === 'string' ? c : c.name)
        .filter(Boolean)
        .map(n => `concept:${n!.toLowerCase().trim().replace(/\s+/g, '-')}`)

      for (let i = 0; i < concepts.length; i++) {
        for (let j = i + 1; j < concepts.length; j++) {
          const pairKey = [concepts[i], concepts[j]].sort().join('|')
          conceptPairs.set(pairKey, (conceptPairs.get(pairKey) || 0) + 1)
        }
      }
    }

    for (const [pairKey, count] of conceptPairs) {
      const [a, b] = pairKey.split('|')
      if (nodeMap.has(a) && nodeMap.has(b)) {
        edgeList.push({
          source: a,
          target: b,
          relation: 'related_to',
          weight: Math.min(count * 0.3, 1.0),
          id: `edge-${edgeIdx++}`,
        })
      }
    }
  }

  // Calculate degree for each node
  const degreeMap = new Map<string, number>()
  for (const e of edgeList) {
    const s = typeof e.source === 'string' ? e.source : (e.source as GraphNode).id
    const t = typeof e.target === 'string' ? e.target : (e.target as GraphNode).id
    degreeMap.set(s, (degreeMap.get(s) || 0) + 1)
    degreeMap.set(t, (degreeMap.get(t) || 0) + 1)
  }

  // Build enriched nodes
  // Build manifest lookup for provenance data
  const manifestMap = new Map<string, ManifestItem>()
  for (const m of manifests) {
    manifestMap.set(m.id, m)
  }

  const enrichedNodes: SemanticNode[] = Array.from(nodeMap.values()).map((n) => {
    const node: SemanticNode = {
      ...n,
      degree: degreeMap.get(n.id) || 0,
    }
    if (n.node_type === 'concept') {
      const clusterKey = n.label.toLowerCase().trim()
      const cluster = conceptClusters.get(clusterKey)
      if (cluster) {
        node.conceptData = cluster
        node.degree = Math.max(node.degree, cluster.sourceCount)
      }
    }
    // Attach provenance to source nodes from manifest
    if (n.node_type === 'source' || n.node_type === 'summary') {
      const m = manifestMap.get(n.id)
      if (m?.compiled_summary?.provenance) {
        node.provenance = m.compiled_summary.provenance.overall_label
        node.provenanceConfidence = m.compiled_summary.provenance.confidence
      }
    }
    return node
  })

  const conceptNodes = enrichedNodes.filter(n => n.node_type === 'concept').length
  const sourceNodes = enrichedNodes.filter(n => n.node_type === 'source').length
  const summaryNodes = enrichedNodes.filter(n => n.node_type === 'summary').length

  return {
    nodes: enrichedNodes,
    edges: edgeList,
    conceptClusters,
    stats: {
      totalNodes: enrichedNodes.length,
      conceptNodes,
      sourceNodes,
      summaryNodes,
      totalEdges: edgeList.length,
    },
  }
}

// ── 视图模式过滤 ────────────────────────────────────────
export type ViewMode = 'concept' | 'document' | 'mixed'

export function filterGraphByView(graph: SemanticGraph, view: ViewMode): SemanticGraph {
  if (view === 'mixed') return graph

  const keepTypes = view === 'concept'
    ? new Set(['concept'])
    : new Set(['source', 'summary'])

  const nodeIds = new Set(graph.nodes.filter(n => keepTypes.has(n.node_type)).map(n => n.id))

  const filteredNodes = graph.nodes.filter(n => keepTypes.has(n.node_type))

  const filteredEdges = graph.edges.filter(e => {
    const s = typeof e.source === 'string' ? e.source : (e.source as SemanticNode).id
    const t = typeof e.target === 'string' ? e.target : (e.target as SemanticNode).id
    return nodeIds.has(s) && nodeIds.has(t)
  })

  return { ...graph, nodes: filteredNodes, edges: filteredEdges }
}

// ── 搜索高亮 ────────────────────────────────────────────
export function searchNodes(nodes: SemanticNode[], query: string): Set<string> {
  if (!query.trim()) return new Set()
  const q = query.toLowerCase()
  return new Set(
    nodes
      .filter(n => n.label.toLowerCase().includes(q))
      .map(n => n.id)
  )
}

// ── 节点半径计算 ────────────────────────────────────────
export function nodeRadius(node: SemanticNode): number {
  const base = node.node_type === 'concept' ? 10 : 7
  const bonus = Math.min(node.degree * 1.5, 14)
  return base + bonus
}
