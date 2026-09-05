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

export interface Citation {
  ref: string
  manifest_id?: string | null
  source: string
  channel: string
  text_hash: string
  score: number
}

export interface QueryResponse {
  query: string
  mode: string
  concepts: SearchResult[]
  summaries: SearchResult[]
  vector_results: SearchResult[]
  search_sources: string[]
  /** 后端可能返回 null（无回答），消费方必须判空 */
  answer: string | null
  time_seconds: number
  reranked?: boolean
  citations?: Citation[]
  unresolved_refs?: string[]
  warnings?: string[]
  timings?: Record<string, number>
  trace_id?: string
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

export interface CompileFailureDetail {
  src_id: string
  error: string
}

export interface CompileResponse {
  job_id: string | null
  status: string
  message: string
  total: number
  processed: number
  compiled: number
  failed: number
  current_files: string[]
  failed_files: string[]
  failure_details: CompileFailureDetail[]
  cancel_requested: boolean
  concurrency: number
  limit: number | null
  attempt: number
  retry_of: string | null
  retryable: boolean
  error: string | null
  created_at: string | null
  started_at: string | null
  finished_at: string | null
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
  /** 后端 metadata 为任意 JSON 值（string/number/bool/list/object），渲染前必须格式化 */
  metadata?: Record<string, unknown>
}

/** 将任意 JSON metadata 值格式化为可安全渲染的字符串 */
export function formatMetadataValue(value: unknown): string {
  if (value == null) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
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
