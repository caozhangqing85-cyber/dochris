import type {
  StatusResponse,
  QueryResponse,
  CompileRequest,
  CompileResponse,
  GraphResponse,
  GraphNodeDetail,
  GraphSearchResult,
  ManifestItem,
  AppConfig,
  PromoteResponse,
  SearchResult,
} from '@/types'

const BASE = '/api/v1'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
    signal: options?.signal,
  })
  if (!res.ok) {
    let msg: string
    try {
      const err = await res.json()
      msg = typeof err.detail === 'string' ? err.detail
        : Array.isArray(err.detail) ? err.detail.map((d: any) => d.msg ?? '').join('; ')
        : err.error || `Request failed: ${res.status}`
    } catch {
      msg = `Request failed: ${res.status}`
    }
    throw new Error(msg)
  }
  return res.json()
}

// ── Status ──────────────────────────────────────────────
export const getStatus = () => request<StatusResponse>('/status')

// ── Query ───────────────────────────────────────────────
export const queryKnowledge = (q: string, mode = 'combined', topK = 5, contribute = false) =>
  request<QueryResponse>(`/query?q=${encodeURIComponent(q)}&mode=${mode}&top_k=${topK}${contribute ? '&contribute=true' : ''}`)

export interface StreamCallbacks {
  onMeta?: (meta: { query: string; mode: string; search_sources: string[]; time_seconds: number }) => void
  onResults?: (data: {
    concepts: SearchResult[]
    summaries: SearchResult[]
    vector_results: SearchResult[]
  }) => void
  onRerank?: (data: { reranked: boolean }) => void
  onChunk?: (text: string) => void
  onDone?: (finalTime: number, traceId?: string) => void
  onError?: (error: string) => void
}

export const queryKnowledgeStream = async (
  q: string,
  mode = 'combined',
  topK = 5,
  callbacks: StreamCallbacks = {},
  rerank = false,
  contribute = false,
  signal?: AbortSignal,
): Promise<void> => {
  const url = `${BASE}/query/stream?q=${encodeURIComponent(q)}&mode=${mode}&top_k=${topK}${rerank ? '&rerank=true' : ''}${contribute ? '&contribute=true' : ''}`
  const res = await fetch(url, { headers: { Accept: 'text/event-stream' }, signal: signal ?? AbortSignal.timeout(120000) })
  if (!res.ok) {
    // 404 触发降级；其他错误也统一 throw（让 catch 走降级或显示错误）
    if (res.status === 404) throw new Error('STREAM_NOT_AVAILABLE')
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `Request failed: ${res.status}`)
  }

  const reader = res.body?.getReader()
  if (!reader) { callbacks.onError?.('No response body'); return }

  const decoder = new TextDecoder()
  let buffer = ''

  // SSE 事件累加器：按空行（事件边界）切分
  // 每个 SSE 事件由若干行 field:value 组成，以一个空行结束
  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // 按空行切分出完整的事件块（兼容 \n\n 和 \r\n\r\n）
    let sepIndex: number
    while ((sepIndex = buffer.search(/\r?\n\r?\n/)) !== -1) {
      const eventBlock = buffer.slice(0, sepIndex)
      buffer = buffer.slice(sepIndex).replace(/^\r?\n\r?\n/, '')

      // 解析事件块内的 field:value 行
      const lines = eventBlock.split(/\r?\n/)
      let eventName = ''
      const dataLines: string[] = []
      for (const line of lines) {
        if (line.startsWith('event:')) {
          eventName = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          // SSE 规范：多个 data: 行用 \n 连接还原原文
          dataLines.push(line.slice(5).replace(/^ /, ''))
        }
      }
      if (!eventName || dataLines.length === 0) continue

      dispatchEvent(eventName, dataLines.join('\n'), callbacks)
    }
  }

  // 处理残余 buffer：连接关闭时最后事件可能无结尾空行，避免 done 事件丢失
  const trailing = buffer.trim()
  if (trailing) {
    const lines = trailing.split(/\r?\n/)
    let eventName = ''
    const dataLines: string[] = []
    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).replace(/^ /, ''))
      }
    }
    if (eventName && dataLines.length > 0) {
      dispatchEvent(eventName, dataLines.join('\n'), callbacks)
    }
  }
}

/** 按 SSE 事件名分发到对应回调。
 *
 * answer_delta 为纯文本（不经 JSON 编码），其余事件为 JSON。
 * 事件名与后端 src/dochris/api/sse.py QueryStreamEventName 对齐。
 */
function dispatchEvent(
  eventName: string,
  rawData: string,
  callbacks: StreamCallbacks,
): void {
  try {
    switch (eventName) {
      case 'meta': {
        const parsed = JSON.parse(rawData)
        callbacks.onMeta?.(parsed)
        break
      }
      case 'retrieval': {
        const parsed = JSON.parse(rawData)
        callbacks.onResults?.(parsed)
        break
      }
      case 'rerank': {
        const parsed = JSON.parse(rawData)
        callbacks.onRerank?.(parsed)
        break
      }
      case 'answer_delta': {
        // answer_delta 是纯文本，不 JSON 解析
        callbacks.onChunk?.(rawData)
        break
      }
      case 'done': {
        const parsed = JSON.parse(rawData)
        callbacks.onDone?.(parsed?.time_seconds ?? 0, parsed?.trace_id)
        break
      }
      case 'error': {
        const parsed = JSON.parse(rawData)
        callbacks.onError?.(parsed?.message ?? rawData)
        break
      }
      default:
        // ping 等心跳事件忽略
        break
    }
  } catch {
    // JSON 解析失败：对非 answer_delta 事件，回退到原文
    if (eventName === 'error') callbacks.onError?.(rawData)
  }
}

// ── Compile ─────────────────────────────────────────────
export const startCompile = (body: CompileRequest) =>
  request<CompileResponse>('/compile', { method: 'POST', body: JSON.stringify(body) })

// ── Graph ───────────────────────────────────────────────
export const getGraph = () => request<GraphResponse>('/graph')
export const getGraphNode = (nodeId: string) => request<GraphNodeDetail>(`/graph/node/${encodeURIComponent(nodeId)}`)
export const searchGraph = (q: string) => request<GraphSearchResult>(`/graph/search?q=${encodeURIComponent(q)}`)

// ── Manifests ───────────────────────────────────────────
export async function getManifests(): Promise<ManifestItem[]> {
  return request<ManifestItem[]>('/manifests')
}

// ── Files ───────────────────────────────────────────────
export async function uploadFiles(files: File[]): Promise<{ saved: number; ingested: number; failed: number }> {
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f))
  const res = await fetch(`${BASE}/files/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || err.error || `Upload failed: ${res.status}`)
  }
  return res.json()
}

// ── Config ──────────────────────────────────────────────
export const getConfig = () => request<AppConfig>('/config')
export const updateConfig = (config: Partial<AppConfig>) =>
  request<AppConfig>('/config', { method: 'PUT', body: JSON.stringify(config) })

// ── Quality ─────────────────────────────────────────────
export const resetLowQuality = () =>
  request<{ reset_count: number }>('/quality/reset', { method: 'POST' })

// ── Manifests Reset ─────────────────────────────────────
export const resetFailedFiles = () =>
  request<{ reset_count: number }>('/manifests/reset-failed', { method: 'POST' })

// ── Recompile ──────────────────────────────────────────
export interface RecompileStatus {
  running: boolean
  total?: number
  processed?: number
  success?: number
  failed?: number
}
export const getRecompileStatus = () =>
  request<RecompileStatus>('/recompile/status')
export const recompileStale = (limit: number = 10, model?: string) =>
  request<{ queued: number }>(`/recompile/stale?limit=${limit}${model ? `&model=${model}` : ''}`, {
    method: 'POST',
  })

// ── Promote ─────────────────────────────────────────────
export const promoteFile = (srcId: string, target: 'wiki' | 'curated' = 'wiki') =>
  request<PromoteResponse>(`/promote/${srcId}`, { method: 'POST', body: JSON.stringify({ target }) })

// ── Contribution（Query-as-Contribution）──────────────────
export interface CandidateMeta {
  id: string
  title: string
  source_type?: string
  query?: string
  query_mode?: string
  content_hash?: string
  quality_score: number
  status: 'candidate' | 'promoted' | 'discarded'
  needs_review?: boolean
  contradiction?: Record<string, unknown>
  source_manifest_ids?: string[]
  concepts_extracted?: unknown[]
  concepts_referenced?: unknown[]
  created_at?: string
  answer?: string
}
export const getCandidates = (status?: 'candidate' | 'promoted' | 'discarded', needsReviewOnly: boolean = false) =>
  request<{ candidates: CandidateMeta[]; total: number }>('/candidates' + (status ? `?status=${status}${needsReviewOnly ? '&needs_review_only=true' : ''}` : ''))
export const promoteCandidate = (candidateId: string) =>
  request<{ success: boolean; reason?: string }>(`/candidates/${candidateId}/promote`, { method: 'POST' })
export const discardCandidate = (candidateId: string, reason: string = 'manual_discard') =>
  request<{ success: boolean; reason?: string }>(`/candidates/${candidateId}/discard?reason=${encodeURIComponent(reason)}`, { method: 'POST' })

// ── Schema Evolution ─────────────────────────────────
export const enrichSchemaFromGraph = () =>
  request<Record<string, unknown>>('/schema/enrich', { method: 'POST' })
export const autoTagSchema = () =>
  request<Record<string, unknown>>('/schema/auto-tag', { method: 'POST' })
export const checkStaleSchema = () =>
  request<Record<string, unknown>>('/schema/stale')

// ── Metrics ──────────────────────────────────────────
// /metrics 返回 Prometheus 文本格式，不用 JSON
export const getMetrics = () =>
  fetch('/api/v1/metrics', { headers: { Accept: 'text/plain' } }).then(r => r.text())
