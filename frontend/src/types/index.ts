export interface SystemInfo {
  python_version: string
  platform: string
  disk_usage_bytes: number
  disk_total_bytes: number
}

export interface StatusResponse {
  workspace: string
  version: string
  manifests: {
    total: number
    ingested: number
    compiled: number
    failed: number
    promoted_to_wiki: number
    promoted: number
    by_type: Record<string, number>
    trust_levels: Record<string, number>
    concepts_count: number
    summaries_count: number
  }
  config: {
    model: string
    api_base: string
    max_concurrency: number
    min_quality_score: number
    has_api_key: boolean
    query_model: string
    llm_provider: string
    workspace: string
    temperature: number
  }
  system: SystemInfo
}

export interface QueryResponse {
  query: string
  mode: string
  concepts: SearchResult[]
  summaries: SearchResult[]
  vector_results: VectorResult[]
  search_sources: string[]
  answer: string
  time_seconds: number
}

export interface SearchResult {
  title: string
  content: string
  source: string
  file_path: string
  manifest_id: string
  score?: number
}

export interface VectorResult extends SearchResult {
  score: number
}

export interface CompileRequest {
  limit: number
  concurrency: number
  dry_run: boolean
}

export interface CompileResponse {
  status: string
  message: string
  total: number
  compiled: number
  failed: number
}

export interface PromoteRequest {
  target: 'wiki' | 'curated'
}

export interface PromoteResponse {
  src_id: string
  target: string
  success: boolean
  message: string
}

export interface GraphResponse {
  success: boolean
  data: {
    nodes: GraphNode[]
    edges: GraphEdge[]
  }
  version: string
}

/** Node types matching backend: source | concept | summary */
export type GraphNodeType = 'source' | 'concept' | 'summary'

export interface GraphNode {
  id: string
  label: string
  node_type: GraphNodeType
  metadata?: Record<string, string>
}

/** Semantic relation types from backend */
export type GraphRelationType = 'compiled_to' | 'contains_concept' | 'related_to' | 'same_type'

export interface GraphEdge {
  source: string
  target: string
  relation: GraphRelationType
  weight: number
}

/** Node detail from /graph/node/{id} */
export interface GraphNodeDetail {
  success: boolean
  data: {
    node: GraphNode
    neighbors: GraphNode[]
    neighbor_count: number
  }
  version: string
}

/** Graph search result */
export interface GraphSearchResult {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

/** Frontend-enriched concept node (derived from manifests) */
export interface ConceptCluster {
  id: string
  name: string
  explanation?: string
  sourceCount: number
  sources: Array<{ id: string; title: string }>
}

/** Layer 0: Provenance label for compiled content */
export type ProvenanceLabel = 'extracted' | 'merged' | 'inferred' | 'ambiguous'

/** Provenance data embedded in compiled_summary */
export interface ProvenanceData {
  overall_label: ProvenanceLabel
  confidence: number
  summary_label: ProvenanceLabel
  concepts: Array<{
    name: string
    label: ProvenanceLabel
    source_match?: string
  }>
  signals: string[]
}

/** Layer 1: Lint issue severity */
export type LintSeverity = 'error' | 'warning' | 'info'

/** Single lint issue */
export interface LintIssue {
  rule: string
  severity: LintSeverity
  message: string
  detail?: string
}

/** Lint result embedded in compiled_summary */
export interface LintData {
  passed: boolean
  score: number
  error_count: number
  warning_count: number
  info_count: number
  issues: LintIssue[]
}

export interface ManifestItem {
  id: string
  title: string
  type: string
  status: string
  quality_score: number | null
  file_path: string
  size_bytes: number
  original_filename: string
  error_message?: string
  compiled_summary?: {
    one_line: string
    key_points: string[]
    detailed_summary: string
    concepts: Array<string | { name: string; explanation?: string }>
    quality_score: number
    provenance?: ProvenanceData
    lint?: LintData
  }
}

export interface AppConfig {
  api_base: string
  api_key: string
  model: string
  query_model: string
  llm_provider: string
  temperature: number
  workspace: string
  vector_store: string
}

// Re-export graph types for convenience
export type { SemanticNode, SemanticEdge, ViewMode } from '@/lib/graphBuilder'
