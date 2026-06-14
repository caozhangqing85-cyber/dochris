import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import {
  Search, Loader2, Brain, Sparkles, Database, FileText,
  BookmarkPlus, BookmarkCheck, ChevronDown,
  MessageSquare, Tag, Zap, ToggleLeft, ToggleRight,
  X, History, Star, Download,
} from 'lucide-react'
import { queryKnowledge, queryKnowledgeStream, getManifests } from '@/lib/api'
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
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<QueryResponse | null>(null)
  const [error, setError] = useState('')
  const [files, setFiles] = useState<ManifestItem[]>([])
  const [elapsed, setElapsed] = useState(0)

  // UI state
  const [activeTab, setActiveTab] = useState<ResultTab>('answer')
  const [showHistory, setShowHistory] = useState(false)
  const [history, setHistory] = useState<HistoryEntry[]>(loadHistory())
  const [favorites, setFavorites] = useState<FavoriteEntry[]>(loadFavorites())
  const [showModeDropdown, setShowModeDropdown] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const modeRef = useRef<HTMLDivElement>(null)

  // Load files
  const loadFiles = useCallback(async () => {
    try { setFiles(await getManifests()) } catch { /* */ }
  }, [])
  useEffect(() => { loadFiles() }, [loadFiles])

  // filter 包进 useMemo（compiledFiles 每次渲染新引用会破坏下游 memo）
  const compiledFiles = useMemo(
    () => files.filter(f => f.status === 'compiled' || f.status === 'promoted' || f.status === 'promoted_to_wiki'),
    [files]
  )
  const quickQuestions = useMemo(() => generateQuickQuestions(compiledFiles), [compiledFiles])

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

  // Query execution
  const handleQuery = useCallback(async (q?: string, overrideMode?: string) => {
    const queryText = q || query
    if (!queryText.trim()) return
    const useMode = overrideMode || mode
    setLoading(true); setError(''); setResult(null); setElapsed(0); setActiveTab('answer')
    if (!q) setQuery(queryText)
    const start = Date.now()

    // combined/all 模式优先使用流式查询，不可用时降级到传统查询
    if (useMode === 'combined' || useMode === 'all') {
      let fullAnswer = ''
      let streamResult: QueryResponse | null = null

      try {
        await queryKnowledgeStream(queryText, useMode, topK, {
          onMeta: (meta) => {
            streamResult = {
              query: meta.query, mode: meta.mode,
              concepts: [], summaries: [], vector_results: [],
              search_sources: meta.search_sources,
              answer: '', time_seconds: meta.time_seconds,
            }
          },
          onResults: (data) => {
            if (streamResult) {
              streamResult.concepts = data.concepts
              streamResult.summaries = data.summaries
              streamResult.vector_results = data.vector_results as VectorResult[]
              setResult({ ...streamResult, answer: fullAnswer || '' })
            }
          },
          onChunk: (text) => {
            fullAnswer += text
            if (streamResult) {
              setResult({ ...streamResult, answer: fullAnswer })
            }
          },
          onDone: (finalTime) => {
            const elapsedSec = (Date.now() - start) / 1000
            setElapsed(Math.round(elapsedSec * 10) / 10)
            if (streamResult) {
              const finalRes = { ...streamResult, answer: fullAnswer, time_seconds: finalTime || elapsedSec }
              setResult(finalRes)
              const entry: HistoryEntry = {
                query: queryText, mode: useMode, timestamp: Date.now(),
                answerPreview: fullAnswer.slice(0, 80),
              }
              // 函数式更新：避免依赖 history 闭包（防快速连查时旧闭包覆盖新历史）
              setHistory(prev => {
                const newHistory = [entry, ...prev.filter(h => h.query !== queryText)].slice(0, MAX_HISTORY)
                saveHistory(newHistory)
                return newHistory
              })
            }
            setLoading(false)
          },
          onError: (error) => {
            setError(error)
            setLoading(false)
          },
        })
      } catch (e) {
        // stream 端点不可用（404），自动降级到传统查询
        if ((e as Error).message === 'STREAM_NOT_AVAILABLE') {
          try {
            const res = await queryKnowledge(queryText, useMode, topK, contribute)
            const elapsedSec = (Date.now() - start) / 1000
            setElapsed(Math.round(elapsedSec * 10) / 10)
            setResult(res)
            const entry: HistoryEntry = {
              query: queryText, mode: useMode, timestamp: Date.now(),
              answerPreview: res.answer?.slice(0, 80) || '',
            }
            setHistory(prev => {
              const newHistory = [entry, ...prev.filter(h => h.query !== queryText)].slice(0, MAX_HISTORY)
              saveHistory(newHistory)
              return newHistory
            })
          } catch (fallbackErr) { setError((fallbackErr as Error).message) }
          finally { setLoading(false) }
        } else {
          setError((e as Error).message)
          setLoading(false)
        }
      }
    } else {
      // 非 combined 模式使用传统查询
      try {
        const res = await queryKnowledge(queryText, useMode, topK, contribute)
        const elapsedSec = (Date.now() - start) / 1000
        setElapsed(Math.round(elapsedSec * 10) / 10)
        setResult(res)
        const entry: HistoryEntry = {
          query: queryText, mode: useMode, timestamp: Date.now(),
          answerPreview: res.answer?.slice(0, 80) || '',
        }
        setHistory(prev => {
          const newHistory = [entry, ...prev.filter(h => h.query !== queryText)].slice(0, MAX_HISTORY)
          saveHistory(newHistory)
          return newHistory
        })
      } catch (e) { setError((e as Error).message) }
      finally { setLoading(false) }
    }
  }, [query, mode, topK, contribute])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleQuery() }
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
              {compiledFiles.length > 0 && (
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', fontWeight: 400 }}>
                  {compiledFiles.length} 个已编译文档可查询
                </span>
              )}
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
                  <div key={h.timestamp} onClick={() => { setQuery(h.query); setMode(h.mode); handleQuery(h.query, h.mode) }}
                    style={{ padding: 'var(--space-2) var(--space-3)', borderRadius: '4px', cursor: 'pointer', marginBottom: '1px' }}
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
                  </div>
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
                    <div key={`${f.query}-${f.mode || ''}-${f.timestamp}`} onClick={() => { setQuery(f.query); handleQuery(f.query, f.mode) }}
                      style={{ padding: 'var(--space-2) var(--space-3)', borderRadius: '4px', cursor: 'pointer', marginBottom: '1px' }}
                      onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                      onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                    >
                      <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>{f.query}</span>
                    </div>
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
                <button onClick={() => setShowModeDropdown(!showModeDropdown)}
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
                  <div style={{
                    position: 'absolute', top: '100%', left: 0, marginTop: '4px',
                    background: 'var(--bg-card)', border: '1px solid var(--border-default)',
                    borderRadius: 'var(--radius-lg)', boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
                    minWidth: '240px', zIndex: 50, overflow: 'hidden',
                  }}>
                    {MODES.map((m) => (
                      <button key={m.value} onClick={() => { setMode(m.value); setShowModeDropdown(false) }}
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
            </div>

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
            {/* Show streaming answer */}
            {activeTab === 'answer' && result.answer && (
              <div style={{
                borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
                border: '1px solid var(--border-default)', background: 'var(--bg-card)',
              }}>
                <StreamingMarkdown content={result.answer} streaming={loading} />
              </div>
            )}
          </>
        )}

        {/* ── Error ── */}
        {error && (
          <div style={{
            padding: 'var(--space-4)', borderRadius: '4px', marginBottom: 'var(--space-4)',
            background: 'var(--status-error-bg)', color: 'var(--status-error)', fontSize: 'var(--text-sm)',
            display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
          }}>
            <X size={14} /> {error}
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
