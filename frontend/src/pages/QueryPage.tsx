import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import {
  Search, Loader2, Brain, Sparkles, Database, FileText,
  BookmarkPlus, BookmarkCheck, ChevronDown,
  MessageSquare, Tag, Zap, ToggleLeft, ToggleRight,
  X, History, Star, Download, AlertTriangle,
} from 'lucide-react'
import { queryKnowledge, queryKnowledgeStream, contributeQueryResult, getManifests, ApiError } from '@/lib/api'
import type { ContributionMeta, PhaseTimings, StreamErrorEvent } from '@/lib/api'
import type { QueryResponse, ManifestItem, SearchResult, VectorResult } from '@/types'
import ErrorBoundary from '@/components/ui/ErrorBoundary'
import StreamingMarkdown from '@/components/StreamingMarkdown'

// ── 常量 ──────────────────────────────────────────────

const MODES = [
  { value: 'combined', label: '综合', icon: Sparkles, desc: 'AI 回答 + 概念 + 摘要 + 向量' },
  { value: 'concept', label: '概念', icon: Tag, desc: '在提取的概念中搜索' },
  { value: 'summary', label: '摘要', icon: FileText, desc: '在编译摘要中搜索' },
  { value: 'vector', label: '向量', icon: Database, desc: '语义相似度检索' },
  { value: 'all', label: '全量', icon: Search, desc: '搜索全部数据源' },
] as const

const HISTORY_KEY = 'dochris-query-history'
const FAVORITES_KEY = 'dochris-query-favorites'
const MAX_HISTORY = 30

type QueryErrorKind = 'OFFLINE' | 'UNAUTHORIZED' | 'FORBIDDEN' | 'TIMEOUT' | 'ABORTED' | 'HTTP' | 'UNKNOWN'

interface QueryErrorView {
  kind: QueryErrorKind
  title: string
  message: string
  diagnostic: string
  retryable: boolean
}

function formatQueryError(error: unknown): QueryErrorView {
  if (error instanceof ApiError) {
    if (error.code === 'OFFLINE') {
      return {
        kind: 'OFFLINE',
        title: '无法连接后端 API',
        message: error.message,
        diagnostic: '请确认后端服务已启动，或检查前端代理配置。',
        retryable: true,
      }
    }
    if (error.code === 'TIMEOUT') {
      return {
        kind: 'TIMEOUT',
        title: '查询超时',
        message: error.message,
        diagnostic: '本次生成耗时过长。可以减少检索数量，或稍后重试。',
        retryable: true,
      }
    }
    if (error.code === 'ABORTED') {
      return {
        kind: 'ABORTED',
        title: '查询已取消',
        message: '已停止当前流式回答。',
        diagnostic: '可以调整问题后重新查询。',
        retryable: true,
      }
    }
    if (error.status === 401 || error.code === 'UNAUTHORIZED') {
      return {
        kind: 'UNAUTHORIZED',
        title: '未授权',
        message: error.message,
        diagnostic: '请检查本地 API Key 设置。',
        retryable: false,
      }
    }
    if (error.status === 403 || error.code === 'FORBIDDEN') {
      return {
        kind: 'FORBIDDEN',
        title: '没有访问权限',
        message: error.message,
        diagnostic: '当前 API Key 没有执行该查询的权限。',
        retryable: false,
      }
    }
    return {
      kind: 'HTTP',
      title: error.status && error.status >= 500 ? '后端服务异常' : '查询失败',
      message: error.message,
      diagnostic: error.status ? `HTTP ${error.status}` : '后端返回了非预期错误。',
      retryable: !error.status || error.status >= 500,
    }
  }

  const message = error instanceof Error ? error.message : String(error)
  return {
    kind: 'UNKNOWN',
    title: '查询失败',
    message,
    diagnostic: '前端无法识别该错误类型，请查看后端日志。',
    retryable: true,
  }
}

function phaseLabel(key: string): string {
  const labels: Record<string, string> = {
    retrieval: '检索',
    retrieval_seconds: '检索',
    search: '检索',
    rerank: '重排序',
    rerank_seconds: '重排序',
    generation: '生成',
    generation_seconds: '生成',
    contribution: '贡献写入',
    contribution_seconds: '贡献写入',
    total: '总计',
    total_seconds: '总计',
    first_token_seconds: '首字',
  }
  return labels[key] ?? key
}

function streamErrorCodeToApiCode(error: StreamErrorEvent): string {
  const code = error.code?.toUpperCase()
  if (code === 'TIMEOUT' || code === 'TIMEOUT_ERROR') return 'TIMEOUT'
  if (code === 'UNAUTHORIZED' || code === 'AUTH_REQUIRED') return 'UNAUTHORIZED'
  if (code === 'FORBIDDEN') return 'FORBIDDEN'
  return code ?? 'HTTP'
}

// ── Local Storage Helpers ─────────────────────────────

interface HistoryEntry {
  query: string
  mode: string
  timestamp: number
  answerPreview: string
}

interface FavoriteEntry {
  query: string
  mode?: string
  answer: string
  timestamp: number
}

function loadHistory(): HistoryEntry[] {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') }
  catch { return [] }
}

function saveHistory(entries: HistoryEntry[]) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(entries.slice(0, MAX_HISTORY)))
}

function loadFavorites(): FavoriteEntry[] {
  try { return JSON.parse(localStorage.getItem(FAVORITES_KEY) || '[]') }
  catch { return [] }
}

function saveFavorites(entries: FavoriteEntry[]) {
  localStorage.setItem(FAVORITES_KEY, JSON.stringify(entries))
}

// ── Quick Questions ───────────────────────────────────

function generateQuickQuestions(files: ManifestItem[]): string[] {
  const questions: string[] = []
  const concepts = new Set<string>()

  for (const f of files) {
    if (!f.compiled_summary?.concepts) continue
    for (const c of f.compiled_summary.concepts) {
      const name = typeof c === 'string' ? c : c.name
      if (name) concepts.add(name)
    }
  }

  const conceptArr = Array.from(concepts).slice(0, 5)
  if (conceptArr.length > 0) {
    questions.push(`${conceptArr[0]}的核心原理是什么？`)
    questions.push(`${conceptArr.slice(0, 2).join('与')}有什么关系？`)
  }
  if (files.length > 0) {
    questions.push('知识库中覆盖了哪些主要主题？')
    questions.push('总结所有文档的核心要点')
  }
  if (conceptArr.length > 2) {
    questions.push(`比较${conceptArr[1]}和${conceptArr[2]}的异同`)
  }
  questions.push('有哪些重要的学习资源？')

  return questions.slice(0, 5)
}

// ── Highlight Helper ──────────────────────────────────

function highlightText(text: string, query: string): React.ReactNode {
  if (!query.trim()) return text
  const q = query.trim().toLowerCase()
  const lower = text.toLowerCase()
  const idx = lower.indexOf(q)
  if (idx === -1) return text
  return (
    <>
      {text.slice(0, idx)}
      <mark style={{ background: 'var(--color-primary-bg)', color: 'inherit', padding: '0 1px', borderRadius: '2px' }}>
        {text.slice(idx, idx + q.length)}
      </mark>
      {text.slice(idx + q.length)}
    </>
  )
}

// ── Sub-components ────────────────────────────────────

function SourceBadge({ source }: { source: string }) {
  const config: Record<string, { color: string; bg: string; label: string }> = {
    wiki: { color: 'var(--color-primary)', bg: 'var(--color-primary-bg)', label: 'Wiki' },
    outputs: { color: 'var(--status-success)', bg: 'var(--status-success-bg)', label: 'Outputs' },
    vector: { color: 'var(--status-info)', bg: 'var(--status-info-bg)', label: 'Vector' },
    concept: { color: 'var(--status-success)', bg: 'var(--status-success-bg)', label: 'Concept' },
    summary: { color: '#7c3aed', bg: 'rgba(124,58,237,0.08)', label: 'Summary' },
  }
  const c = config[source] || { color: 'var(--text-dimmed)', bg: 'var(--bg-elevated)', label: source }
  return (
    <span style={{
      display: 'inline-flex', padding: '1px 6px', borderRadius: 'var(--radius-full)',
      fontSize: '10px', fontWeight: 600, letterSpacing: '0.125px',
      background: c.bg, color: c.color,
    }}>{c.label}</span>
  )
}

function ResultCard({ result, query }: { result: SearchResult | VectorResult; query: string }) {
  const score = 'score' in result ? result.score : undefined
  return (
    <div style={{
      padding: 'var(--space-4)', borderRadius: 'var(--radius-lg)',
      background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
      transition: 'border-color 120ms ease',
    }}
      onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--border-default)'}
      onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--border-subtle)'}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-1)', gap: 'var(--space-2)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', minWidth: 0, flex: 1 }}>
          <FileText size={13} style={{ color: 'var(--text-dimmed)', flexShrink: 0 }} />
          <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{result.title}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0 }}>
          {result.source && <SourceBadge source={result.source} />}
          {score != null && (
            <span style={{
              fontSize: 'var(--text-xs)', fontWeight: 600,
              color: score >= 0.8 ? 'var(--status-success)' : score >= 0.5 ? 'var(--status-info)' : 'var(--text-dimmed)',
            }}>{Math.round(Math.min(100, Math.max(0, score)) * 100)}%</span>
          )}
        </div>
      </div>
      <p style={{
        fontSize: 'var(--text-sm)', color: 'var(--text-muted)', margin: 0, fontWeight: 400,
        lineHeight: 'var(--leading-relaxed)',
        overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical' as const,
      }}>
        {highlightText(result.content?.slice(0, 300) || '', query)}
      </p>
      {result.file_path && (
        <div style={{ marginTop: 'var(--space-2)', fontSize: '10px', color: 'var(--text-dimmed)', fontWeight: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {result.file_path}
        </div>
      )}
    </div>
  )
}

// ── Main Component ────────────────────────────────────

type ResultTab = 'answer' | 'documents' | 'concepts' | 'vector'

export default function QueryPage() {
  // Query state
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState('combined')
  const [topK, setTopK] = useState(5)
  const [contribute, setContribute] = useState(false)
  const [rerank, setRerank] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<QueryResponse | null>(null)
  // AbortController：新查询取消上一次流式请求，防竞态
  const abortRef = useRef<AbortController | null>(null)
  // 请求序号：降级/非流式路径无 abort 信号，用单调递增序号丢弃过期响应
  const requestSeqRef = useRef(0)
  const [error, setError] = useState('')
  const [queryError, setQueryError] = useState<QueryErrorView | null>(null)
  const [files, setFiles] = useState<ManifestItem[]>([])
  const [filesLoaded, setFilesLoaded] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [contributionReceipt, setContributionReceipt] = useState<ContributionMeta | null>(null)
  const [phaseTimings, setPhaseTimings] = useState<PhaseTimings | null>(null)
  const [degradationNotice, setDegradationNotice] = useState<string | null>(null)
  const [cancellable, setCancellable] = useState(false)

  // UI state
  const [activeTab, setActiveTab] = useState<ResultTab>('answer')
  const [showHistory, setShowHistory] = useState(false)
  const [history, setHistory] = useState<HistoryEntry[]>(loadHistory())
  const [favorites, setFavorites] = useState<FavoriteEntry[]>(loadFavorites())
  const [showModeDropdown, setShowModeDropdown] = useState(false)
  const [focusedModeIndex, setFocusedModeIndex] = useState(0)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const modeRef = useRef<HTMLDivElement>(null)
  const modeTriggerRef = useRef<HTMLButtonElement>(null)
  const modeOptionRefs = useRef<Array<HTMLButtonElement | null>>([])

  useEffect(() => {
    let cancelled = false
    const loadInitialFiles = async () => {
      try {
        const nextFiles = await getManifests()
        if (!cancelled) setFiles(nextFiles)
      } catch { /* */ }
      finally {
        if (!cancelled) setFilesLoaded(true)
      }
    }
    void loadInitialFiles()
    return () => { cancelled = true }
  }, [])

  // filter 包进 useMemo（compiledFiles 每次渲染新引用会破坏下游 memo）
  const compiledFiles = useMemo(
    () => files.filter(f => f.status === 'compiled' || f.status === 'promoted' || f.status === 'promoted_to_wiki'),
    [files]
  )
  const availabilityText = !filesLoaded
    ? '正在读取可查询文档…'
    : compiledFiles.length > 0
      ? `${compiledFiles.length} 个已编译文档可查询`
      : '暂无已编译文档，请先前往文件编译页'
  const quickQuestions = useMemo(() => generateQuickQuestions(compiledFiles), [compiledFiles])
  const phaseTimingItems = useMemo(
    () => Object.entries(phaseTimings ?? {})
      .filter(([, value]) => Number.isFinite(value))
      .map(([key, value]) => ({ key, label: phaseLabel(key), value })),
    [phaseTimings],
  )

  // Click outside to close mode dropdown
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (modeRef.current && !modeRef.current.contains(e.target as Node)) {
        setShowModeDropdown(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  useEffect(() => {
    if (!showModeDropdown) return
    const focusOption = requestAnimationFrame(() => modeOptionRefs.current[focusedModeIndex]?.focus())
    return () => cancelAnimationFrame(focusOption)
  }, [focusedModeIndex, showModeDropdown])

  const closeModeDropdown = useCallback((restoreFocus = true) => {
    setShowModeDropdown(false)
    if (restoreFocus) requestAnimationFrame(() => modeTriggerRef.current?.focus())
  }, [])

  const selectMode = useCallback((nextMode: string, index: number) => {
    setMode(nextMode)
    setFocusedModeIndex(index)
    closeModeDropdown()
  }, [closeModeDropdown])

  const openModeDropdown = () => {
    const selectedIndex = Math.max(0, MODES.findIndex((item) => item.value === mode))
    setFocusedModeIndex(selectedIndex)
    setShowModeDropdown(true)
  }

  const toggleModeDropdown = () => {
    if (showModeDropdown) setShowModeDropdown(false)
    else openModeDropdown()
  }

  const handleModeTriggerKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
    event.preventDefault()
    openModeDropdown()
  }

  const handleModeOptionKeyDown = (
    event: React.KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      closeModeDropdown()
      return
    }
    if (event.key === 'Tab') {
      setShowModeDropdown(false)
      return
    }

    const direction = event.key === 'ArrowDown'
      ? 1
      : event.key === 'ArrowUp'
        ? -1
        : 0
    if (direction === 0) return

    event.preventDefault()
    const nextIndex = (index + direction + MODES.length) % MODES.length
    setFocusedModeIndex(nextIndex)
    modeOptionRefs.current[nextIndex]?.focus()
  }

  // Query execution
  const showQueryError = useCallback((nextError: unknown) => {
    const view = formatQueryError(nextError)
    setQueryError(view)
    setError(view.message)
  }, [])

  const persistContribution = useCallback(async (queryResult: QueryResponse) => {
    if (!contribute || !queryResult.answer) return
    try {
      const receipt = await contributeQueryResult(queryResult)
      setContributionReceipt(receipt)
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : String(nextError)
      setError(`回答已生成，但贡献写入失败：${message}`)
    }
  }, [contribute])

  const handleCancelQuery = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setCancellable(false)
    setLoading(false)
    setQueryError(null)
    setError('')
    setResult(null)
    setElapsed(0)
    setContributionReceipt(null)
    setPhaseTimings(null)
  }, [])

  const handleQuery = useCallback(async (q?: string, overrideMode?: string) => {
    const queryText = q || query
    if (!queryText.trim()) return
    const useMode = overrideMode || mode
    requestSeqRef.current += 1
    const seq = requestSeqRef.current
    const isCurrent = () => seq === requestSeqRef.current
    setLoading(true); setError(''); setQueryError(null); setResult(null); setElapsed(0); setContributionReceipt(null); setPhaseTimings(null); setDegradationNotice(null); setCancellable(false); setActiveTab('answer')
    if (!q) setQuery(queryText)
    const start = Date.now()

    // combined/all 模式优先使用流式查询，不可用时降级到传统查询
    if (useMode === 'combined' || useMode === 'all') {
      let fullAnswer = ''
      let streamResult: QueryResponse | null = null
      let ctrl: AbortController | null = null

      try {
        // 取消上一次流式请求，防竞态
        abortRef.current?.abort()
        ctrl = new AbortController()
        abortRef.current = ctrl
        setCancellable(true)
        const isActiveRequest = () => abortRef.current === ctrl
        await queryKnowledgeStream(queryText, {
          mode: useMode,
          topK,
          rerank,
          signal: ctrl.signal,
          callbacks: {
            onMeta: (meta) => {
              if (!isActiveRequest()) return
              streamResult = {
                query: meta.query, mode: meta.mode,
                concepts: [], summaries: [], vector_results: [],
                search_sources: meta.search_sources,
                answer: '', time_seconds: meta.time_seconds,
              }
            },
            onResults: (data) => {
              if (!isActiveRequest()) return
              if (streamResult) {
                streamResult.concepts = data.concepts
                streamResult.summaries = data.summaries
                streamResult.vector_results = data.vector_results as VectorResult[]
                setResult({ ...streamResult, answer: fullAnswer || '' })
              }
            },
            onWarning: (warning) => {
              if (!isActiveRequest()) return
              setDegradationNotice(warning.message)
            },
            onChunk: (text) => {
              if (!isActiveRequest()) return
              fullAnswer += text
              if (streamResult) {
                setResult({ ...streamResult, answer: fullAnswer })
              }
            },
            onDone: (finalTime, _traceId, _legacyContributionMeta, donePhaseTimings, done) => {
              if (!isActiveRequest()) return
              const elapsedSec = finalTime || (Date.now() - start) / 1000
              setElapsed(Math.round(elapsedSec * 10) / 10)
              setPhaseTimings(donePhaseTimings ?? null)
              // done.final_answer 是后端清理后的最终答案，与非流式完全一致；
              // 用它替换增量拼接文本，保证两种模式结果相同
              const finalAnswer = done?.final_answer ?? fullAnswer
              if (streamResult) {
                const finalRes: QueryResponse = {
                  ...streamResult,
                  answer: finalAnswer,
                  time_seconds: finalTime || elapsedSec,
                  citations: (done?.citations ?? []).map(c => ({
                    ref: c.ref,
                    manifest_id: c.manifest_id ?? null,
                    source: c.source ?? '',
                    channel: c.channel ?? '',
                    text_hash: c.text_hash ?? '',
                    score: c.score ?? 0,
                  })),
                  unresolved_refs: done?.unresolved_refs ?? [],
                }
                setResult(finalRes)
                void persistContribution(finalRes)
                const entry: HistoryEntry = {
                  query: queryText, mode: useMode, timestamp: Date.now(),
                  answerPreview: finalAnswer.slice(0, 80),
                }
                // 函数式更新：避免依赖 history 闭包（防快速连查时旧闭包覆盖新历史）
                setHistory(prev => {
                  const newHistory = [entry, ...prev.filter(h => h.query !== queryText)].slice(0, MAX_HISTORY)
                  saveHistory(newHistory)
                  return newHistory
                })
              }
              setLoading(false)
              setCancellable(false)
              abortRef.current = null
            },
            onError: (error, detail) => {
              if (!isActiveRequest()) return
              if (detail?.phase_timings) setPhaseTimings(detail.phase_timings)
              showQueryError(new ApiError(error, { code: detail ? streamErrorCodeToApiCode(detail) : 'HTTP' }))
              setLoading(false)
              setCancellable(false)
              abortRef.current = null
            },
          },
        })
      } catch (e) {
        const wasCurrentRequest = ctrl !== null && abortRef.current === ctrl
        // stream 端点不可用（404），自动降级到传统查询
        if ((e as Error).message === 'STREAM_NOT_AVAILABLE') {
          if (wasCurrentRequest) {
            setCancellable(false)
            abortRef.current = null
          }
          try {
            const res = await queryKnowledge(queryText, useMode, topK, rerank)
            if (!isCurrent()) return
            const elapsedSec = (Date.now() - start) / 1000
            setElapsed(Math.round(elapsedSec * 10) / 10)
            setResult(res)
            await persistContribution(res)
            const entry: HistoryEntry = {
              query: queryText, mode: useMode, timestamp: Date.now(),
              answerPreview: res.answer?.slice(0, 80) || '',
            }
            setHistory(prev => {
              const newHistory = [entry, ...prev.filter(h => h.query !== queryText)].slice(0, MAX_HISTORY)
              saveHistory(newHistory)
              return newHistory
            })
          } catch (fallbackErr) { showQueryError(fallbackErr) }
          finally { setLoading(false); setCancellable(false) }
        } else {
          if (e instanceof ApiError && e.code === 'ABORTED') return
          showQueryError(e)
          setLoading(false)
          setCancellable(false)
          if (wasCurrentRequest) abortRef.current = null
        }
      }
    } else {
      abortRef.current?.abort()
      abortRef.current = null
      setCancellable(false)
      // 非 combined 模式使用传统查询
      const seq = ++requestSeqRef.current
      const isCurrent = () => seq === requestSeqRef.current
      try {
        const res = await queryKnowledge(queryText, useMode, topK, rerank)
        if (!isCurrent()) return
        const elapsedSec = (Date.now() - start) / 1000
        setElapsed(Math.round(elapsedSec * 10) / 10)
        setResult(res)
        await persistContribution(res)
        const entry: HistoryEntry = {
          query: queryText, mode: useMode, timestamp: Date.now(),
          answerPreview: res.answer?.slice(0, 80) || '',
        }
        setHistory(prev => {
          const newHistory = [entry, ...prev.filter(h => h.query !== queryText)].slice(0, MAX_HISTORY)
          saveHistory(newHistory)
          return newHistory
        })
      } catch (e) { showQueryError(e) }
      finally { setLoading(false) }
    }
  }, [query, mode, topK, rerank, loading, showQueryError, persistContribution])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!loading) handleQuery()
    }
  }

  // Favorites
  // 收藏键用 query+mode 组合，允许同一查询在不同模式下分别收藏
  const favKey = (q: string, m: string) => `${q}@@${m}`
  const isFavorited = result ? favorites.some(f => favKey(f.query, f.mode || '') === favKey(result.query, result.mode)) : false
  const toggleFavorite = () => {
    if (!result?.answer) return
    if (isFavorited) {
      const newFavs = favorites.filter(f => favKey(f.query, f.mode || '') !== favKey(result.query, result.mode))
      setFavorites(newFavs); saveFavorites(newFavs)
    } else {
      const newFavs = [{ query: result.query, mode: result.mode, answer: result.answer, timestamp: Date.now() }, ...favorites]
      setFavorites(newFavs); saveFavorites(newFavs)
    }
  }

  const clearHistory = () => { setHistory([]); saveHistory([]) }

  const exportMarkdown = () => {
    if (!result?.answer) return
    const lines = [
      `# ${result.query}`,
      '',
      `> 查询模式: ${result.mode} | 耗时: ${elapsed}s`,
      '',
      result.answer,
    ]
    if (result.concepts?.length) {
      lines.push('', '## 相关概念', '')
      result.concepts.forEach(c => {
        lines.push(`- **${c.title}**: ${c.content?.slice(0, 100) || ''}`)
      })
    }
    if (result.summaries?.length) {
      lines.push('', '## 相关文档', '')
      result.summaries.forEach(s => {
        lines.push(`### ${s.title}`, s.content?.slice(0, 200) || '', '')
      })
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `query-${Date.now()}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const tabCounts = useMemo(() => ({
    answer: result?.answer ? 1 : 0,
    documents: (result?.summaries?.length || 0) + (result?.vector_results?.length || 0),
    concepts: result?.concepts?.length || 0,
    vector: result?.vector_results?.length || 0,
  }), [result])

  const currentModeConfig = MODES.find(m => m.value === mode) || MODES[0]

  // ── Render ──────────────────────────────────────────

  return (
    <ErrorBoundary fallback={<div style={{ padding: '24px', textAlign: 'center', color: 'var(--status-error)' }}>页面渲染出错，请刷新</div>}>
      <div className="page-container" style={{ padding: 'var(--space-12) var(--space-10)', maxWidth: '100%', margin: '0 auto' }}>

        {/* ── Header ── */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-5)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <Brain size={22} style={{ color: 'var(--color-primary)' }} />
            <div>
              <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.25px', margin: 0 }}>知识查询</h1>
              <span
                id="query-availability-status"
                role="status"
                aria-live="polite"
                style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', fontWeight: 400 }}
              >
                {availabilityText}
              </span>
            </div>
          </div>
          <button onClick={() => setShowHistory(!showHistory)} title="查询历史"
            style={{
              padding: '6px 12px', borderRadius: '4px', border: '1px solid',
              borderColor: showHistory ? 'var(--color-primary)' : 'var(--border-default)',
              background: showHistory ? 'var(--color-primary-bg)' : 'transparent',
              color: showHistory ? 'var(--color-primary)' : 'var(--text-muted)',
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px',
              fontSize: 'var(--text-sm)', fontWeight: 500,
            }}>
            <History size={14} /> 查询历史
            {history.length > 0 && (
              <span style={{ fontSize: '10px', padding: '0 5px', borderRadius: 'var(--radius-full)', background: 'var(--bg-elevated)', fontWeight: 600 }}>{history.length}</span>
            )}
          </button>
        </div>

        {/* ── History Panel (shown above main content when toggled) ── */}
        {showHistory && (
          <div style={{
            borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-default)',
            marginBottom: 'var(--space-4)', background: 'var(--bg-card)',
            maxHeight: '240px', overflow: 'hidden', display: 'flex',
          }}>
            {/* History list */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div style={{ padding: 'var(--space-3) var(--space-4)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', flexShrink: 0 }}>
                <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-dimmed)' }}>最近查询</span>
                {history.length > 0 && (
                  <button onClick={clearHistory} style={{ padding: '2px 6px', borderRadius: '3px', border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-dimmed)', fontSize: 'var(--text-xs)' }}>
                    清空
                  </button>
                )}
              </div>
              <div style={{ flex: 1, overflow: 'auto', padding: 'var(--space-2)' }}>
                {history.length === 0 ? (
                  <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', textAlign: 'center', padding: 'var(--space-4)' }}>暂无查询历史</p>
                ) : history.map((h) => (
                  <button key={h.timestamp} type="button"
                    aria-label={`重新运行历史查询：${h.query}`}
                    onClick={() => { setQuery(h.query); setMode(h.mode); handleQuery(h.query, h.mode) }}
                    style={{ width: '100%', padding: 'var(--space-2) var(--space-3)', borderRadius: '4px', border: 'none', background: 'transparent', cursor: 'pointer', marginBottom: '1px', textAlign: 'left' }}
                    onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                      <MessageSquare size={11} style={{ color: 'var(--text-dimmed)', flexShrink: 0 }} />
                      <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{h.query}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginTop: '2px', marginLeft: '18px' }}>
                      <span style={{ fontSize: '10px', color: 'var(--text-dimmed)' }}>{new Date(h.timestamp).toLocaleDateString()}</span>
                      <span style={{ fontSize: '10px', padding: '0 4px', borderRadius: 'var(--radius-full)', background: 'var(--bg-elevated)', color: 'var(--text-dimmed)' }}>{h.mode}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
            {/* Favorites */}
            {favorites.length > 0 && (
              <div style={{ width: '220px', flexShrink: 0, borderLeft: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                <div style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--border-subtle)', flexShrink: 0 }}>
                  <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-dimmed)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Star size={10} /> 收藏
                  </span>
                </div>
                <div style={{ flex: 1, overflow: 'auto', padding: 'var(--space-2)' }}>
                  {favorites.map((f) => (
                    <button key={`${f.query}-${f.mode || ''}-${f.timestamp}`} type="button"
                      aria-label={`运行收藏查询：${f.query}`}
                      onClick={() => { setQuery(f.query); if (f.mode) setMode(f.mode); handleQuery(f.query, f.mode) }}
                      style={{ width: '100%', padding: 'var(--space-2) var(--space-3)', borderRadius: '4px', border: 'none', background: 'transparent', cursor: 'pointer', marginBottom: '1px', textAlign: 'left' }}
                      onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                      onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                    >
                      <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>{f.query}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Query Input Area ── */}
        <div style={{
          borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)',
          border: '1px solid var(--border-default)', marginBottom: 'var(--space-4)',
          background: 'var(--bg-card)', boxShadow: 'var(--shadow-sm)',
        }}>
          <textarea
            ref={textareaRef}
            aria-label="查询知识库"
            aria-describedby="query-availability-status"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={compiledFiles.length > 0 ? "输入问题或关键词，搜索知识库... (Enter 发送, Shift+Enter 换行)" : "知识库中暂无已编译文件，请先编译文件后再查询"}
            rows={3}
            style={{
              width: '100%', background: 'transparent', outline: 'none', resize: 'none',
              fontSize: 'var(--text-base)', lineHeight: 'var(--leading-normal)',
              color: 'var(--text-primary)', border: 'none',
              fontFamily: 'var(--font-sans)', fontWeight: 400,
            }}
          />

          {/* Controls bar */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
              {/* Mode selector — dropdown opens DOWNWARD below the button */}
              <div ref={modeRef} style={{ position: 'relative' }}>
                <button ref={modeTriggerRef} id="query-mode-trigger" type="button"
                  aria-label={`选择查询模式，当前${currentModeConfig.label}`}
                  aria-haspopup="listbox" aria-expanded={showModeDropdown}
                  aria-controls="query-mode-listbox"
                  onClick={toggleModeDropdown}
                  onKeyDown={handleModeTriggerKeyDown}
                  style={{
                    padding: '4px 10px', borderRadius: '4px', fontSize: 'var(--text-sm)', fontWeight: 500,
                    border: '1px solid var(--border-default)', background: 'var(--bg-elevated)',
                    color: 'var(--text-secondary)', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: '4px',
                  }}>
                  <currentModeConfig.icon size={12} /> {currentModeConfig.label}
                  <ChevronDown size={10} style={{ transform: showModeDropdown ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 150ms' }} />
                </button>
                {showModeDropdown && (
                  <div id="query-mode-listbox" role="listbox" aria-labelledby="query-mode-trigger" style={{
                    position: 'absolute', top: '100%', left: 0, marginTop: '4px',
                    background: 'var(--bg-card)', border: '1px solid var(--border-default)',
                    borderRadius: 'var(--radius-lg)', boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
                    minWidth: '240px', zIndex: 50, overflow: 'hidden',
                  }}>
                    {MODES.map((m, index) => (
                      <button key={m.value} ref={(element) => { modeOptionRefs.current[index] = element }}
                        type="button" role="option" aria-selected={mode === m.value}
                        tabIndex={focusedModeIndex === index ? 0 : -1}
                        onClick={() => selectMode(m.value, index)}
                        onKeyDown={(event) => handleModeOptionKeyDown(event, index)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 'var(--space-3)',
                          padding: 'var(--space-3) var(--space-4)', width: '100%', border: 'none',
                          background: mode === m.value ? 'var(--color-primary-bg)' : 'transparent',
                          color: mode === m.value ? 'var(--color-primary)' : 'var(--text-secondary)',
                          cursor: 'pointer', textAlign: 'left', fontSize: 'var(--text-sm)',
                        }}>
                        <m.icon size={14} style={{ flexShrink: 0 }} />
                        <div>
                          <div style={{ fontWeight: 600 }}>{m.label}</div>
                          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', fontWeight: 400 }}>{m.desc}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Top K */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', fontWeight: 400 }}>数量: {topK}</span>
                <input type="range" min={1} max={20} value={topK} onChange={(e) => setTopK(+e.target.value)}
                  style={{ width: '60px', accentColor: 'var(--color-primary)' }} />
              </div>

              {/* Contribute toggle */}
              <button onClick={() => setContribute(!contribute)} title="Query-as-Contribution：将回答写回知识库"
                style={{
                  padding: '4px 10px', borderRadius: '4px', fontSize: 'var(--text-xs)', fontWeight: 500,
                  border: '1px solid', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px',
                  borderColor: contribute ? 'var(--status-success)' : 'var(--border-default)',
                  background: contribute ? 'var(--status-success-bg)' : 'transparent',
                  color: contribute ? 'var(--status-success)' : 'var(--text-dimmed)',
                }}>
                {contribute ? <ToggleRight size={14} /> : <ToggleLeft size={14} />}
                贡献模式
              </button>

              {/* Reranker toggle */}
              <button onClick={() => setRerank(!rerank)} title="启用 Reranker 重排序（CrossEncoder 精排）"
                style={{
                  padding: '4px 10px', borderRadius: '4px', fontSize: 'var(--text-xs)', fontWeight: 500,
                  border: '1px solid', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px',
                  borderColor: rerank ? 'var(--color-primary)' : 'var(--border-default)',
                  background: rerank ? 'var(--color-primary-bg)' : 'transparent',
                  color: rerank ? 'var(--color-primary)' : 'var(--text-dimmed)',
                }}>
                {rerank ? <ToggleRight size={14} /> : <ToggleLeft size={14} />}
                重排序
              </button>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              {loading && cancellable && (
                <button onClick={handleCancelQuery}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: '6px',
                    padding: '8px 14px', borderRadius: '4px',
                    fontSize: 'var(--text-sm)', fontWeight: 600,
                    color: 'var(--status-error)', background: 'var(--status-error-bg)',
                    border: '1px solid rgba(220,38,38,0.18)', cursor: 'pointer',
                  }}>
                  <X size={14} />
                  <span>取消</span>
                </button>
              )}

              {/* Search button */}
              <button onClick={() => handleQuery()} disabled={loading || !query.trim() || compiledFiles.length === 0}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: '6px',
                  padding: '8px 20px', borderRadius: '4px',
                  fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--bg-card)',
                  background: 'var(--color-primary)', border: 'none', cursor: 'pointer',
                  opacity: loading || !query.trim() || compiledFiles.length === 0 ? 0.4 : 1,
                }}>
                {loading ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
                查询
              </button>
            </div>
          </div>
        </div>

        {/* ── Quick Questions (only show when no result) ── */}
        {!result && !loading && !error && compiledFiles.length > 0 && quickQuestions.length > 0 && (
          <div style={{ marginBottom: 'var(--space-5)' }}>
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-dimmed)', marginBottom: 'var(--space-3)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Zap size={11} /> 快捷提问
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
              {quickQuestions.map((q, i) => (
                <button key={i} onClick={() => { setQuery(q); handleQuery(q) }}
                  className="quick-question-btn"
                  style={{
                    padding: '6px 14px', borderRadius: 'var(--radius-full)',
                    fontSize: 'var(--text-sm)', fontWeight: 500,
                    border: '1px solid var(--border-default)', background: 'var(--bg-card)',
                    color: 'var(--text-secondary)', cursor: 'pointer',
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Loading / Streaming ── */}
        {loading && !result && (
          <div style={{
            borderRadius: 'var(--radius-lg)', padding: 'var(--space-10)',
            textAlign: 'center', border: '1px solid var(--border-default)',
            background: 'var(--bg-card)',
          }}>
            <div style={{ position: 'relative', width: '48px', height: '48px', margin: '0 auto var(--space-4)' }}>
              <Loader2 size={48} className="animate-spin" style={{ color: 'var(--color-primary)', position: 'absolute', inset: 0 }} />
              <Brain size={20} style={{ color: 'var(--color-primary)', position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }} />
            </div>
            <p style={{ fontSize: 'var(--text-base)', color: 'var(--text-primary)', fontWeight: 600, margin: 0 }}>AI 正在检索知识库并生成回答...</p>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-dimmed)', marginTop: 'var(--space-1)' }}>使用 {currentModeConfig.label} 模式检索中</p>
            {cancellable && (
              <button onClick={handleCancelQuery}
                style={{
                  marginTop: 'var(--space-4)', display: 'inline-flex', alignItems: 'center', gap: '6px',
                  padding: '7px 14px', borderRadius: '4px', fontSize: 'var(--text-sm)', fontWeight: 600,
                  color: 'var(--status-error)', background: 'var(--status-error-bg)',
                  border: '1px solid rgba(220,38,38,0.18)', cursor: 'pointer',
                }}>
                <X size={14} />
                <span>取消</span>
              </button>
            )}
          </div>
        )}
        {/* Streaming: result 正在逐步接收 */}
        {loading && result && (
          <>
            {/* Result header (reuse existing result header with streaming indicator) */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-3)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
                <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-dimmed)' }}>
                  搜索 "<span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{result.query}</span>"
                </span>
                <span style={{ fontSize: 'var(--text-xs)', padding: '2px 8px', borderRadius: 'var(--radius-full)', background: 'var(--color-primary-bg)', color: 'var(--color-primary)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <Loader2 size={10} className="animate-spin" /> 生成中...
                </span>
                {result.search_sources?.length > 0 && (
                  <div style={{ display: 'flex', gap: '2px' }}>
                    {result.search_sources.map(s => <SourceBadge key={s} source={s} />)}
                  </div>
                )}
              </div>
            </div>
            {/* Tab bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)', marginBottom: 'var(--space-4)', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 'var(--space-2)' }}>
              {([
                { key: 'answer' as ResultTab, label: 'AI 回答', count: result.answer ? 1 : 0, icon: Sparkles },
                { key: 'documents' as ResultTab, label: '相关文档', count: (result.summaries?.length || 0) + (result.vector_results?.length || 0), icon: FileText },
                { key: 'concepts' as ResultTab, label: '概念匹配', count: result.concepts?.length || 0, icon: Tag },
                { key: 'vector' as ResultTab, label: '向量检索', count: result.vector_results?.length || 0, icon: Database },
              ]).map((tab) => (
                <button key={tab.key} onClick={() => setActiveTab(tab.key)}
                  style={{
                    padding: '4px 12px', borderRadius: '4px', fontSize: 'var(--text-sm)', fontWeight: 500,
                    border: 'none', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: '4px',
                    background: activeTab === tab.key ? 'var(--color-primary-bg)' : 'transparent',
                    color: activeTab === tab.key ? 'var(--color-primary)' : 'var(--text-dimmed)',
                  }}>
                  <tab.icon size={12} /> {tab.label}
                  <span style={{
                    fontSize: '10px', padding: '0 5px', borderRadius: 'var(--radius-full)',
                    background: activeTab === tab.key ? 'var(--color-primary)' : 'var(--bg-elevated)',
                    color: activeTab === tab.key ? 'var(--bg-card)' : 'var(--text-dimmed)',
                    fontWeight: 600, lineHeight: '16px',
                  }}>{tab.count}</span>
                </button>
              ))}
            </div>
            {/* Tab content */}
            {activeTab === 'answer' && result.answer && (
              <div style={{
                borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
                border: '1px solid var(--border-default)', background: 'var(--bg-card)',
              }}>
                <StreamingMarkdown content={result.answer} streaming={loading} />
                {(result.citations?.length || result.unresolved_refs?.length) ? (
                  <div style={{
                    marginTop: 'var(--space-4)', paddingTop: 'var(--space-3)',
                    borderTop: '1px solid var(--border-subtle)',
                  }}>
                    <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-dimmed)', marginBottom: 'var(--space-1)' }}>
                      引用来源
                    </div>
                    <ul style={{ margin: 0, paddingInlineStart: '18px', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                      {(result.citations ?? []).map(c => (
                        <li key={c.ref} style={{ wordBreak: 'break-word' }}>
                          <span style={{ fontWeight: 600 }}>[{c.ref}]</span>
                          {' '}{c.manifest_id || c.source || '未知来源'}
                          {' · '}{c.channel}
                        </li>
                      ))}
                      {(result.unresolved_refs ?? []).length > 0 && (
                        <li style={{ color: 'var(--status-warning)' }}>
                          未匹配来源：{(result.unresolved_refs ?? []).join('、')}
                        </li>
                      )}
                    </ul>
                  </div>
                ) : null}
              </div>
            )}
            {activeTab === 'documents' && result.summaries && result.summaries.length > 0 && (
              <div style={{
                borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
                border: '1px solid var(--border-default)', background: 'var(--bg-card)',
              }}>
                {result.summaries.map(r => <ResultCard key={r.source} result={r} query={result.query} />)}
              </div>
            )}
            {activeTab === 'concepts' && result.concepts && result.concepts.length > 0 && (
              <div style={{
                borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
                border: '1px solid var(--border-default)', background: 'var(--bg-card)',
              }}>
                {result.concepts.map(c => <ResultCard key={c.source} result={c} query={result.query} />)}
              </div>
            )}
            {activeTab === 'vector' && result.vector_results && result.vector_results.length > 0 && (
              <div style={{
                borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
                border: '1px solid var(--border-default)', background: 'var(--bg-card)',
              }}>
                {result.vector_results.map((r, i) => <ResultCard key={i} result={r} query={result.query} />)}
              </div>
            )}
          </>
        )}

        {/* ── Error ── */}
        {queryError && (
          <div style={{
            padding: 'var(--space-4)', borderRadius: '4px', marginBottom: 'var(--space-4)',
            background: 'var(--status-error-bg)', color: 'var(--status-error)', fontSize: 'var(--text-sm)',
            display: 'flex', alignItems: 'flex-start', gap: 'var(--space-2)',
          }}>
            <X size={14} style={{ marginTop: '2px', flexShrink: 0 }} />
            <div>
              <div style={{ fontWeight: 700 }}>{queryError.title}</div>
              <div style={{ marginTop: '2px' }}>{queryError.message}</div>
              <div style={{ marginTop: '4px', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
                {queryError.diagnostic}
                {queryError.retryable ? ' · 可重试' : ''}
              </div>
            </div>
          </div>
        )}

        {degradationNotice && (
          <div style={{
            padding: 'var(--space-3) var(--space-4)', borderRadius: '4px', marginBottom: 'var(--space-4)',
            background: 'var(--status-warning-bg)', color: 'var(--status-warning)', fontSize: 'var(--text-xs)',
            display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
          }} role="status">
            <AlertTriangle size={13} style={{ flexShrink: 0 }} />
            <span>{degradationNotice}</span>
          </div>
        )}

        {contributionReceipt && !loading && (
          <div style={{
            padding: 'var(--space-4)', borderRadius: '4px', marginBottom: 'var(--space-4)',
            background: 'var(--status-success-bg)', color: 'var(--status-success)', fontSize: 'var(--text-sm)',
            display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
          }}>
            <BookmarkCheck size={14} />
            <span>
              {contributionReceipt.auto_promoted ? '回答已自动提升到知识库' : '回答已写入候选区'}
              {' · '}质量分 {contributionReceipt.quality_score}
              {contributionReceipt.needs_review ? ' · 等待审核' : ''}
              {' · '}{contributionReceipt.id}
            </span>
          </div>
        )}

        {/* ── Results Area ── */}
        {result && !loading && (
          <>
            {/* Result header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-3)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
                <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-dimmed)' }}>
                  搜索 "<span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{result.query}</span>"
                </span>
                <span style={{ fontSize: 'var(--text-xs)', padding: '2px 8px', borderRadius: 'var(--radius-full)', background: 'var(--color-primary-bg)', color: 'var(--color-primary)', fontWeight: 600 }}>
                  {elapsed}s
                </span>
                {phaseTimingItems.length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', fontWeight: 600 }}>阶段耗时</span>
                    {phaseTimingItems.map(item => (
                      <span key={item.key} style={{ fontSize: '10px', padding: '1px 6px', borderRadius: 'var(--radius-full)', background: 'var(--bg-elevated)', color: 'var(--text-dimmed)', fontWeight: 600 }}>
                        {item.label} {Math.round(item.value * 10) / 10}s
                      </span>
                    ))}
                  </div>
                )}
                {result.search_sources?.length > 0 && (
                  <div style={{ display: 'flex', gap: '2px' }}>
                    {result.search_sources.map(s => <SourceBadge key={s} source={s} />)}
                  </div>
                )}
              </div>
              {result.answer && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                  <button onClick={exportMarkdown} title="导出为 Markdown 文件"
                    style={{
                      padding: '4px 8px', borderRadius: '4px', border: 'none', cursor: 'pointer',
                      background: 'transparent', color: 'var(--text-dimmed)',
                      display: 'flex', alignItems: 'center', gap: '4px', fontSize: 'var(--text-xs)', fontWeight: 500,
                    }}>
                    <Download size={13} /> 导出
                  </button>
                  <button onClick={toggleFavorite} title={isFavorited ? '取消收藏' : '收藏此回答'}
                    style={{
                      padding: '4px 8px', borderRadius: '4px', border: 'none', cursor: 'pointer',
                      background: 'transparent', color: isFavorited ? '#e5a100' : 'var(--text-dimmed)',
                      display: 'flex', alignItems: 'center', gap: '4px', fontSize: 'var(--text-xs)', fontWeight: 500,
                    }}>
                    {isFavorited ? <BookmarkCheck size={13} /> : <BookmarkPlus size={13} />}
                    {isFavorited ? '已收藏' : '收藏'}
                  </button>
                </div>
              )}
            </div>

            {/* Tab bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)', marginBottom: 'var(--space-4)', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 'var(--space-2)' }}>
              {([
                { key: 'answer' as ResultTab, label: 'AI 回答', count: tabCounts.answer, icon: Sparkles },
                { key: 'documents' as ResultTab, label: '相关文档', count: tabCounts.documents, icon: FileText },
                { key: 'concepts' as ResultTab, label: '概念匹配', count: tabCounts.concepts, icon: Tag },
                { key: 'vector' as ResultTab, label: '向量检索', count: tabCounts.vector, icon: Database },
              ]).map((tab) => (
                <button key={tab.key} onClick={() => setActiveTab(tab.key)}
                  style={{
                    padding: '4px 12px', borderRadius: '4px', fontSize: 'var(--text-sm)', fontWeight: 500,
                    border: 'none', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: '4px',
                    background: activeTab === tab.key ? 'var(--color-primary-bg)' : 'transparent',
                    color: activeTab === tab.key ? 'var(--color-primary)' : 'var(--text-dimmed)',
                  }}>
                  <tab.icon size={12} /> {tab.label}
                  <span style={{
                    fontSize: '10px', padding: '0 5px', borderRadius: 'var(--radius-full)',
                    background: activeTab === tab.key ? 'var(--color-primary)' : 'var(--bg-elevated)',
                    color: activeTab === tab.key ? 'var(--bg-card)' : 'var(--text-dimmed)',
                    fontWeight: 600, lineHeight: '16px',
                  }}>{tab.count}</span>
                </button>
              ))}
            </div>

            {/* Tab content */}
            {/* AI Answer */}
            {activeTab === 'answer' && (
              result.answer ? (
                <div style={{
                  borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
                  border: '1px solid var(--border-default)', background: 'var(--bg-card)',
                }}>
                  <StreamingMarkdown content={result.answer} streaming={false} />
                  {result.search_sources?.length > 0 && (
                    <div style={{ marginTop: 'var(--space-4)', padding: 'var(--space-3)', background: 'var(--bg-elevated)', borderRadius: '4px' }}>
                      <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-dimmed)', marginBottom: 'var(--space-2)' }}>引用来源</div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)' }}>
                        {result.search_sources.map(s => <SourceBadge key={s} source={s} />)}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: 'var(--space-8)', color: 'var(--text-dimmed)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-subtle)' }}>
                  <p style={{ fontSize: 'var(--text-sm)', margin: 0 }}>该查询模式未生成 AI 回答</p>
                  <p style={{ fontSize: 'var(--text-xs)', marginTop: 'var(--space-1)' }}>试试切换到"综合"模式</p>
                </div>
              )
            )}

            {/* Documents tab — 仅展示摘要匹配结果 */}
            {activeTab === 'documents' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                {result.summaries?.length > 0 ? (
                  <>
                    <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-dimmed)' }}>摘要匹配 ({result.summaries.length})</div>
                    {result.summaries.map((r, i) => <ResultCard key={`s-${i}`} result={r} query={result.query} />)}
                  </>
                ) : (
                  <div style={{ textAlign: 'center', padding: 'var(--space-8)', color: 'var(--text-dimmed)', fontSize: 'var(--text-sm)' }}>未找到匹配的摘要文档，试试"向量检索"标签</div>
                )}
              </div>
            )}

            {/* Concepts tab */}
            {activeTab === 'concepts' && (
              result.concepts?.length > 0 ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
                  {result.concepts.map((c, i) => (
                    <div key={i} style={{
                      padding: 'var(--space-3) var(--space-4)', borderRadius: 'var(--radius-lg)',
                      background: 'var(--status-success-bg)', border: '1px solid rgba(26,174,57,0.15)',
                      maxWidth: '320px',
                    }}>
                      <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--status-success)', marginBottom: '4px' }}>{c.title}</div>
                      {c.content && (
                        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', margin: 0, lineHeight: 'var(--leading-relaxed)', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical' as const }}>
                          {c.content}
                        </p>
                      )}
                      {c.source && <div style={{ marginTop: '4px' }}><SourceBadge source={c.source} /></div>}
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: 'var(--space-8)', color: 'var(--text-dimmed)', fontSize: 'var(--text-sm)' }}>未找到匹配的概念</div>
              )
            )}

            {/* Vector tab */}
            {activeTab === 'vector' && (
              result.vector_results?.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                  {result.vector_results.map((r, i) => <ResultCard key={i} result={r} query={result.query} />)}
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: 'var(--space-8)', color: 'var(--text-dimmed)', fontSize: 'var(--text-sm)' }}>未找到语义相似的结果</div>
              )
            )}
          </>
        )}

        {/* ── Empty State ── */}
        {!result && !error && !loading && compiledFiles.length > 0 && quickQuestions.length === 0 && (
          <div style={{ textAlign: 'center', padding: 'var(--space-10)', color: 'var(--text-dimmed)' }}>
            <Brain size={32} style={{ marginBottom: 'var(--space-3)' }} />
            <p style={{ fontSize: 'var(--text-base)', color: 'var(--text-muted)', fontWeight: 500, margin: 0 }}>输入问题开始查询</p>
            <p style={{ fontSize: 'var(--text-sm)', margin: 'var(--space-1) 0 0' }}>支持自然语言提问或关键词搜索</p>
          </div>
        )}
        {!result && !error && !loading && compiledFiles.length === 0 && (
          <div style={{ textAlign: 'center', padding: 'var(--space-10)', color: 'var(--text-dimmed)' }}>
            <Database size={32} style={{ marginBottom: 'var(--space-3)' }} />
            <p style={{ fontSize: 'var(--text-base)', color: 'var(--text-muted)', fontWeight: 500, margin: 0 }}>知识库为空</p>
            <p style={{ fontSize: 'var(--text-sm)', margin: 'var(--space-1) 0 0' }}>请先上传文件并编译后再查询</p>
          </div>
        )}
      </div>
    </ErrorBoundary>
  )
}
