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
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || err.error || `Request failed: ${res.status}`)
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
  onChunk?: (text: string) => void
  onDone?: (finalTime: number) => void
  onError?: (error: string) => void
}

export const queryKnowledgeStream = async (
  q: string,
  mode = 'combined',
  topK = 5,
  callbacks: StreamCallbacks = {},
): Promise<void> => {
  const url = `${BASE}/query/stream?q=${encodeURIComponent(q)}&mode=${mode}&top_k=${topK}`
  const res = await fetch(url, { headers: { Accept: 'text/event-stream' } })
  if (!res.ok) {
    if (res.status === 404) throw new Error('STREAM_NOT_AVAILABLE')
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    callbacks.onError?.(err.detail || `Request failed: ${res.status}`)
    return
  }

  const reader = res.body?.getReader()
  if (!reader) { callbacks.onError?.('No response body'); return }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    let currentEvent = ''
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim()
      } else if (line.startsWith('data: ') && currentEvent) {
        const data = line.slice(6)
        try {
          const parsed = JSON.parse(data)
          switch (currentEvent) {
            case 'meta': callbacks.onMeta?.(parsed); break
            case 'results': callbacks.onResults?.(parsed); break
            case 'answer': callbacks.onChunk?.(typeof parsed === 'string' ? parsed : String(parsed)); break
            case 'done': callbacks.onDone?.(parsed?.time_seconds ?? 0); break
            case 'error': callbacks.onError?.(typeof parsed === 'string' ? parsed : JSON.stringify(parsed)); break
          }
        } catch { /* ignore malformed JSON */ }
        currentEvent = ''
      }
    }
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

// ── Promote ─────────────────────────────────────────────
export const promoteFile = (srcId: string, target: 'wiki' | 'curated' = 'wiki') =>
  request<PromoteResponse>(`/promote/${srcId}`, { method: 'POST', body: JSON.stringify({ target }) })
