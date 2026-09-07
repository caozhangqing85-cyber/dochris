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

export type ApiErrorCode = 'HTTP' | 'UNAUTHORIZED' | 'FORBIDDEN' | 'OFFLINE' | 'TIMEOUT' | 'ABORTED' | string

export class ApiError extends Error {
  status?: number
  code: ApiErrorCode

  constructor(message: string, { status, code = 'HTTP' }: { status?: number; code?: ApiErrorCode } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

interface ErrorDetails {
  message: string
  code?: string
}

const API_KEY_STORAGE_KEY = 'dochris_api_key'

export function getApiAccessKey(): string {
  try {
    return localStorage.getItem(API_KEY_STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

export function setApiAccessKey(value: string): void {
  try {
    const normalized = value.trim()
    if (normalized) {
      localStorage.setItem(API_KEY_STORAGE_KEY, normalized)
    } else {
      localStorage.removeItem(API_KEY_STORAGE_KEY)
    }
  } catch {
    // Storage can be unavailable in restricted/private browser contexts.
  }
}

function toHeaderRecord(headers?: HeadersInit): Record<string, string> {
  if (!headers) return {}
  if (headers instanceof Headers) return Object.fromEntries(headers.entries())
  if (Array.isArray(headers)) return Object.fromEntries(headers)
  return Object.fromEntries(
    Object.entries(headers).map(([key, value]) => [key, String(value)]),
  )
}

function apiHeaders(
  headers?: HeadersInit,
  protectedHeaders: Record<string, string> = {},
): Record<string, string> {
  const apiKey = getApiAccessKey()
  return {
    ...toHeaderRecord(headers),
    ...protectedHeaders,
    ...(apiKey ? { 'X-API-Key': apiKey } : {}),
  }
}

async function readErrorDetails(res: Response, fallback: string): Promise<ErrorDetails> {
  let text: string
  try {
    text = await res.text()
  } catch {
    return { message: fallback }
  }
  if (!text) return { message: fallback }

  try {
    const body = JSON.parse(text)
    const code = typeof body.code === 'string' ? body.code : undefined
    if (typeof body.detail === 'string') return { message: body.detail, code }
    if (Array.isArray(body.detail)) {
      return {
        message: body.detail.map((item: { msg?: string }) => item.msg ?? '').filter(Boolean).join('; ') || fallback,
        code,
      }
    }
    if (typeof body.error === 'string') return { message: body.error, code }
  } catch {
    // JSON 解析失败：区分网关/代理返回的 HTML 错误页（展示干净提示）
    // 和有意义的纯文本错误（如 nginx 的 plain text 或后端自定义信息）
    if (text.trimStart().startsWith('<')) {
      const hint = res.status >= 500
        ? '服务端暂时不可用，请稍后重试'
        : res.status >= 400
          ? `请求失败（HTTP ${res.status}）`
          : fallback
      return { message: hint, code: statusCodeToErrorCode(res.status) }
    }
    return { message: text, code: statusCodeToErrorCode(res.status) }
  }
  return { message: fallback }
}

async function readErrorMessage(res: Response, fallback: string): Promise<string> {
  return (await readErrorDetails(res, fallback)).message
}

function statusCodeToErrorCode(status: number): ApiErrorCode {
  if (status === 401) return 'UNAUTHORIZED'
  if (status === 403) return 'FORBIDDEN'
  return 'HTTP'
}

function normalizeFetchError(error: unknown): ApiError {
  if (error instanceof DOMException) {
    if (error.name === 'TimeoutError') return new ApiError('请求超时，请稍后重试', { code: 'TIMEOUT' })
    if (error.name === 'AbortError') return new ApiError('请求已取消', { code: 'ABORTED' })
  }
  if (error instanceof TypeError) return new ApiError('无法连接后端 API', { code: 'OFFLINE' })
  if (error instanceof ApiError) return error
  if (error instanceof Error) return new ApiError(error.message, { code: 'HTTP' })
  return new ApiError(String(error), { code: 'HTTP' })
}

function createTimeoutSignal(timeoutMs: number): AbortSignal | undefined {
  if (timeoutMs <= 0) return undefined
  if (typeof AbortSignal.timeout === 'function') return AbortSignal.timeout(timeoutMs)

  const controller = new AbortController()
  setTimeout(() => {
    controller.abort(new DOMException('The operation timed out.', 'TimeoutError'))
  }, timeoutMs)
  return controller.signal
}

function composeAbortSignal(signal?: AbortSignal, timeoutMs = 120000): AbortSignal | undefined {
  const timeoutSignal = createTimeoutSignal(timeoutMs)
  const signals = [signal, timeoutSignal].filter((item): item is AbortSignal => Boolean(item))
  if (signals.length === 0) return undefined
  if (signals.length === 1) return signals[0]
  if (typeof AbortSignal.any === 'function') return AbortSignal.any(signals)

  const controller = new AbortController()
  const abortFrom = (source: AbortSignal) => {
    if (!controller.signal.aborted) controller.abort(source.reason)
  }
  for (const nextSignal of signals) {
    if (nextSignal.aborted) {
      abortFrom(nextSignal)
    } else {
      nextSignal.addEventListener('abort', () => abortFrom(nextSignal), { once: true })
    }
  }
  return controller.signal
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const { headers, ...init } = options ?? {}
  let res: Response
  try {
    res = await fetch(`${BASE}${url}`, {
      ...init,
      headers: apiHeaders(headers, { 'Content-Type': 'application/json' }),
    })
  } catch (error) {
    throw normalizeFetchError(error)
  }
  if (!res.ok) {
    const details = await readErrorDetails(res, `Request failed: ${res.status}`)
    throw new ApiError(details.message, { status: res.status, code: details.code ?? statusCodeToErrorCode(res.status) })
  }
  return res.json()
}

// ── Status ──────────────────────────────────────────────
export const getStatus = () => request<StatusResponse>('/status')

// ── Query ───────────────────────────────────────────────
export const queryKnowledge = (q: string, mode = 'combined', topK = 5, rerank = false) =>
  request<QueryResponse>(`/query?q=${encodeURIComponent(q)}&mode=${mode}&top_k=${topK}${rerank ? '&rerank=true' : ''}`)

export interface ContributionMeta {
  id: string
  quality_score: number
  needs_review: boolean
  auto_promoted: boolean
}

export const contributeQueryResult = (queryResult: QueryResponse) =>
  request<ContributionMeta>('/query/contribution', {
    method: 'POST',
    body: JSON.stringify(queryResult),
  })

export type PhaseTimings = Record<string, number>

/** done 事件携带的结构化引用（与后端 Citation 模型对齐） */
export interface StreamCitation {
  ref: string
  manifest_id?: string | null
  source?: string
  channel?: string
  text_hash?: string
  score?: number
}

export interface StreamDoneEvent {
  time_seconds: number
  trace_id?: string
  contribution?: ContributionMeta
  phase_timings?: PhaseTimings
  /** 与非流式一致的清理后最终答案，收到时应替换增量渲染文本 */
  final_answer?: string
  citations?: StreamCitation[]
  unresolved_refs?: string[]
}

export interface StreamErrorEvent {
  message: string
  code?: string
  trace_id?: string
  phase_timings?: PhaseTimings
}

export interface StreamCallbacks {
  onMeta?: (meta: { query: string; mode: string; search_sources: string[]; time_seconds: number }) => void
  onResults?: (data: {
    concepts: SearchResult[]
    summaries: SearchResult[]
    vector_results: SearchResult[]
  }) => void
  onRerank?: (data: { reranked: boolean }) => void
  /** 非致命降级提示（如 combined 模式向量检索不可用） */
  onWarning?: (warning: { message: string; code?: string }) => void
  onChunk?: (text: string) => void
  onDone?: (
    finalTime: number,
    traceId?: string,
    contribution?: ContributionMeta,
    phaseTimings?: PhaseTimings,
    done?: StreamDoneEvent,
  ) => void
  onDoneDetailed?: (done: StreamDoneEvent) => void
  onError?: (error: string, detail?: StreamErrorEvent) => void
}

export interface QueryStreamOptions {
  mode?: string
  topK?: number
  callbacks?: StreamCallbacks
  rerank?: boolean
  /** @deprecated Contributions are explicit POST mutations after a query completes. */
  contribute?: boolean
  signal?: AbortSignal
  timeoutMs?: number
}

export const queryKnowledgeStream = async (
  q: string,
  modeOrOptions: string | QueryStreamOptions = 'combined',
  topK = 5,
  callbacks: StreamCallbacks = {},
  rerank = false,
  contribute = false,
  signal?: AbortSignal,
): Promise<void> => {
  const options = typeof modeOrOptions === 'string'
    ? { mode: modeOrOptions, topK, callbacks, rerank, contribute, signal, timeoutMs: 120000 }
    : {
        mode: modeOrOptions.mode ?? 'combined',
        topK: modeOrOptions.topK ?? 5,
        callbacks: modeOrOptions.callbacks ?? {},
        rerank: modeOrOptions.rerank ?? false,
        contribute: modeOrOptions.contribute ?? false,
        signal: modeOrOptions.signal,
        timeoutMs: modeOrOptions.timeoutMs ?? 120000,
      }
  const { mode, topK: resolvedTopK, callbacks: resolvedCallbacks, rerank: shouldRerank, signal: requestSignal, timeoutMs } = options
  const url = `${BASE}/query/stream?q=${encodeURIComponent(q)}&mode=${mode}&top_k=${resolvedTopK}${shouldRerank ? '&rerank=true' : ''}`
  let res: Response
  try {
    res = await fetch(url, {
      headers: apiHeaders({ Accept: 'text/event-stream' }),
      signal: composeAbortSignal(requestSignal, timeoutMs),
    })
  } catch (error) {
    throw normalizeFetchError(error)
  }
  if (!res.ok) {
    if (res.status === 404) throw new Error('STREAM_NOT_AVAILABLE')
    const details = await readErrorDetails(res, `Request failed: ${res.status}`)
    throw new ApiError(details.message, { status: res.status, code: details.code ?? statusCodeToErrorCode(res.status) })
  }

  const reader = res.body?.getReader()
  if (!reader) { resolvedCallbacks.onError?.('No response body'); return }

  const decoder = new TextDecoder()
  let buffer = ''
  let terminalSeen = false

  try {
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
        if (terminalSeen) continue

        terminalSeen = dispatchEvent(eventName, dataLines.join('\n'), resolvedCallbacks)
        if (terminalSeen) {
          await reader.cancel().catch(() => undefined)
          return
        }
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
      if (eventName && dataLines.length > 0 && !terminalSeen) {
        terminalSeen = dispatchEvent(eventName, dataLines.join('\n'), resolvedCallbacks)
      }
    }
    if (!terminalSeen) {
      resolvedCallbacks.onError?.('流式响应未完整结束', {
        message: '流式响应未完整结束',
        code: 'STREAM_INCOMPLETE',
      })
    }
  } catch (error) {
    throw normalizeFetchError(error)
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
): boolean {
  try {
    switch (eventName) {
      case 'meta': {
        const parsed = JSON.parse(rawData)
        callbacks.onMeta?.(parsed)
        return false
      }
      case 'retrieval': {
        const parsed = JSON.parse(rawData)
        callbacks.onResults?.(parsed)
        return false
      }
      case 'rerank': {
        const parsed = JSON.parse(rawData)
        callbacks.onRerank?.(parsed)
        return false
      }
      case 'warning': {
        const parsed = JSON.parse(rawData)
        callbacks.onWarning?.({ message: parsed?.message ?? rawData, code: parsed?.code })
        return false
      }
      case 'answer_delta': {
        // answer_delta 是纯文本，不 JSON 解析
        callbacks.onChunk?.(rawData)
        return false
      }
      case 'done': {
        const parsed = JSON.parse(rawData)
        const phaseTimings = parsed?.phase_timings ?? parsed?.timings
        const done: StreamDoneEvent = {
          time_seconds: parsed?.time_seconds ?? 0,
          trace_id: parsed?.trace_id,
          contribution: parsed?.contribution,
          phase_timings: phaseTimings,
        }
        // 仅在存在时附加（保持与旧版 payload 的结构兼容）
        if (parsed?.final_answer !== undefined) done.final_answer = parsed.final_answer
        if (parsed?.citations !== undefined) done.citations = parsed.citations
        if (parsed?.unresolved_refs !== undefined) done.unresolved_refs = parsed.unresolved_refs
        callbacks.onDone?.(done.time_seconds, done.trace_id, done.contribution, done.phase_timings, done)
        callbacks.onDoneDetailed?.(done)
        return true
      }
      case 'error': {
        const parsed = JSON.parse(rawData)
        const detail: StreamErrorEvent = {
          message: parsed?.message ?? parsed?.detail ?? rawData,
          code: parsed?.code,
          trace_id: parsed?.trace_id,
          phase_timings: parsed?.phase_timings ?? parsed?.timings,
        }
        callbacks.onError?.(detail.message, detail)
        return true
      }
      default:
        // ping 等心跳事件忽略
        return false
    }
  } catch {
    // JSON 解析失败：对非 answer_delta 事件，回退到原文
    if (eventName === 'error' || eventName === 'done') {
      callbacks.onError?.('流式响应格式错误', {
        message: '流式响应格式错误',
        code: 'PARSE_ERROR',
      })
    }
    return eventName === 'error' || eventName === 'done'
  }
  return false
}

// ── Compile ─────────────────────────────────────────────
export const startCompile = (body: CompileRequest, idempotencyKey?: string) =>
  request<CompileResponse>('/compile', {
    method: 'POST',
    body: JSON.stringify(body),
    headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
  })
export const getCurrentCompileJob = () => request<CompileResponse>('/compile/jobs/current')
export const getCompileJobs = (limit = 20) =>
  request<CompileResponse[]>(`/compile/jobs?limit=${encodeURIComponent(limit)}`)
export const getCompileJob = (jobId: string) =>
  request<CompileResponse>(`/compile/jobs/${encodeURIComponent(jobId)}`)
export const retryCompileJob = (jobId: string) =>
  request<CompileResponse>(`/compile/jobs/${encodeURIComponent(jobId)}/retry`, {
    method: 'POST',
  })
export const cancelCompileJob = (jobId: string) =>
  request<CompileResponse>(`/compile/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST',
  })

// ── Graph ───────────────────────────────────────────────
export const getGraph = () => request<GraphResponse>('/graph')
export const getGraphNode = (nodeId: string) => request<GraphNodeDetail>(`/graph/node/${encodeURIComponent(nodeId)}`)
export const searchGraph = (q: string) => request<GraphSearchResult>(`/graph/search?q=${encodeURIComponent(q)}`)

// ── Manifests ───────────────────────────────────────────
export async function getManifests(): Promise<ManifestItem[]> {
  return request<ManifestItem[]>('/manifests')
}

// ── Files ───────────────────────────────────────────────
export async function uploadFiles(files: File[]): Promise<{ saved: number; ingested: number; skipped: number; failed: number; errors?: string[] }> {
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f))
  const res = await fetch(`${BASE}/files/upload`, {
    method: 'POST',
    headers: apiHeaders(),
    body: formData,
  })
  if (!res.ok) {
    throw new Error(await readErrorMessage(res, `Upload failed: ${res.status}`))
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
/** 候选详情（UX-03）：全文 + 来源 + 矛盾 + 晋升最终 diff 计划 */
export interface CandidateDetail extends CandidateMeta {
  full_text?: string
  file?: string
  answer_preview?: string
  promoted_to?: string
  promote_plan?: {
    changes: Array<{ path: string; action: string; size_bytes?: number }>
    blockers: string[]
  }
}
export const getCandidateDetail = (candidateId: string) =>
  request<CandidateDetail>(`/candidates/${encodeURIComponent(candidateId)}`)
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
  fetch('/api/v1/metrics', { headers: apiHeaders({ Accept: 'text/plain' }) }).catch((error) => {
    throw normalizeFetchError(error)
  }).then(async (res) => {
    if (!res.ok) throw new Error(await readErrorMessage(res, `Request failed: ${res.status}`))
    return res.text()
  })
