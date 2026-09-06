import { useEffect, useState, useCallback } from 'react'
import {
  PlayCircle, RefreshCw, Loader2, CheckCircle2, XCircle,
  Clock, FileCheck, AlertTriangle, Search, ChevronDown,
  ChevronRight, ChevronLeft, RotateCcw, ArrowUpRight, FileText, Tag,
  Shield, ShieldAlert, ShieldCheck, ShieldQuestion,
} from 'lucide-react'
import {
  ApiError,
  cancelCompileJob,
  getCompileJob,
  getCompileJobs,
  getCurrentCompileJob,
  getManifests,
  getRecompileStatus,
  getStatus,
  promoteFile,
  recompileStale,
  retryCompileJob,
  startCompile,
} from '@/lib/api'
import { compileJobPercent, isCompileJobActive } from '@/lib/compileJob'
import { classifyRequestError, type RequestErrorInfo } from '@/lib/errors'
import { withMinDelay, formatBytes, statusLabel } from '@/lib/utils'
import type { StatusResponse, CompileResponse, ManifestItem } from '@/types'
import StatCard from '@/components/ui/StatCard'
import PageHeader from '@/components/ui/PageHeader'
import RequestErrorState from '@/components/ui/RequestErrorState'
import SectionHeader from '@/components/ui/SectionHeader'
import ErrorBoundary from '@/components/ui/ErrorBoundary'

const STATUS_COLORS: Record<string, { color: string; bg: string }> = {
  ingested: { color: 'var(--status-info)', bg: 'var(--status-info-bg)' },
  compiling: { color: 'var(--status-warning)', bg: 'var(--status-warning-bg)' },
  compiled: { color: 'var(--status-success)', bg: 'var(--status-success-bg)' },
  failed: { color: 'var(--status-error)', bg: 'var(--status-error-bg)' },
  promoted: { color: 'var(--color-primary)', bg: 'var(--color-primary-bg)' },
  promoted_to_wiki: { color: 'var(--color-primary)', bg: 'var(--color-primary-bg)' },
}

const PAGE_SIZE = 20
const JOB_STATUS_LABELS: Record<string, string> = {
  accepted: '已提交',
  queued: '排队中',
  running: '进行中',
  cancelling: '取消中',
  completed: '已完成',
  completed_with_errors: '部分失败',
  failed: '失败',
  cancelled: '已取消',
  interrupted: '服务中断',
}

function formatJobTime(value: string | null) {
  if (!value) return '时间未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date)
}

export default function CompilePage() {
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [allFiles, setAllFiles] = useState<ManifestItem[]>([])
  const [limit, setLimit] = useState(10)
  const [concurrency, setConcurrency] = useState(1)
  const [dryRun, setDryRun] = useState(false)
  const [compiling, setCompiling] = useState(false)
  const [recompiling, setRecompiling] = useState(false)
  const [staleCount, setStaleCount] = useState(0)
  const [refreshing, setRefreshing] = useState(false)
  const [result, setResult] = useState<CompileResponse | null>(null)
  const [compileJob, setCompileJob] = useState<CompileResponse | null>(null)
  const [compileHistory, setCompileHistory] = useState<CompileResponse[]>([])
  const [cancellingCompile, setCancellingCompile] = useState(false)
  const [retryingJobId, setRetryingJobId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [refreshMsg, setRefreshMsg] = useState('')
  const [loadError, setLoadError] = useState<RequestErrorInfo | null>(null)

  // File list state
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('')
  const [selectedFile, setSelectedFile] = useState<ManifestItem | null>(null)
  const [promoting, setPromoting] = useState(false)
  const [promoteMsg, setPromoteMsg] = useState('')
  const [page, setPage] = useState(1)

  const loadData = useCallback(async (isCancelled: () => boolean = () => false) => {
    if (!isCancelled()) setRefreshing(true)
    try {
      const [s, files, recompileStatus] = await Promise.all([
        withMinDelay(getStatus()),
        getManifests(),
        getRecompileStatus(),
      ])
      if (isCancelled()) return false
      setStatus(s)
      setAllFiles(files)
      setStaleCount(
        'stale_count' in recompileStatus && typeof recompileStatus.stale_count === 'number'
          ? recompileStatus.stale_count
          : 0,
      )
      setLoadError(null)
      return true
    } catch (e) {
      if (!isCancelled()) setLoadError(classifyRequestError(e))
      return false
    } finally {
      if (!isCancelled()) setRefreshing(false)
    }
  }, [])

  const loadCompileHistory = useCallback(async (
    isCancelled: () => boolean = () => false,
  ) => {
    try {
      const jobs = await getCompileJobs(10)
      if (isCancelled()) return false
      setCompileHistory(jobs)
      return true
    } catch (e) {
      if (!isCancelled()) setError(`无法加载编译历史：${(e as Error).message}`)
      return false
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    queueMicrotask(() => {
      void (async () => {
        await Promise.all([
          loadData(() => cancelled),
          loadCompileHistory(() => cancelled),
        ])
        try {
          const job = await getCurrentCompileJob()
          if (cancelled) return
          setCompileJob(job)
          setResult(job)
        } catch (e) {
          if (e instanceof ApiError && e.status === 404) return
          if (!cancelled) setError(`无法恢复编译任务：${(e as Error).message}`)
        }
      })()
    })
    return () => { cancelled = true }
  }, [loadCompileHistory, loadData])

  useEffect(() => {
    if (!compileJob?.job_id || !isCompileJobActive(compileJob.status)) return

    let cancelled = false
    const jobId = compileJob.job_id
    const poll = async () => {
      try {
        const next = await getCompileJob(jobId)
        if (cancelled) return
        if (!isCompileJobActive(next.status)) {
          await Promise.all([
            loadData(() => cancelled),
            loadCompileHistory(() => cancelled),
          ])
          if (cancelled) return
        }
        setCompileJob(next)
        setResult(next)
        setError('')
      } catch (e) {
        if (cancelled) return
        if (e instanceof ApiError && e.status === 404) {
          setCompileJob(null)
          setResult(null)
          setError('编译任务已不在当前服务进程中，请重新提交')
          return
        }
        setError(`同步编译进度失败，正在重试：${(e as Error).message}`)
      }
    }

    const timer = window.setInterval(() => { void poll() }, 1000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [compileJob?.job_id, compileJob?.status, loadCompileHistory, loadData])

  const handleRefresh = async () => {
    const [dataOk, historyOk] = await Promise.all([loadData(), loadCompileHistory()])
    const ok = dataOk && historyOk
    setRefreshMsg(ok ? '已刷新' : '刷新失败')
    setTimeout(() => setRefreshMsg(''), 2000)
  }

  const handleCompile = async () => {
    setCompiling(true); setError(''); setResult(null)
    // 幂等键：同一次提交的网络重放不会创建重复任务
    const idempotencyKey = crypto.randomUUID()
    try {
      const res = await startCompile({ limit, concurrency, dry_run: dryRun }, idempotencyKey)
      setResult(res)
      setCompileJob(res.job_id ? res : null)
      if (res.job_id) {
        setCompileHistory((jobs) => [
          res,
          ...jobs.filter((job) => job.job_id !== res.job_id),
        ].slice(0, 10))
      }
      if (!res.job_id || !isCompileJobActive(res.status)) await loadData()
    } catch (e) { setError((e as Error).message) }
    finally { setCompiling(false) }
  }

  const handleCancelCompile = async () => {
    if (!compileJob?.job_id) return
    setCancellingCompile(true); setError('')
    try {
      const next = await cancelCompileJob(compileJob.job_id)
      setCompileJob(next)
      setResult(next)
      setCompileHistory((jobs) => jobs.map((job) => (
        job.job_id === next.job_id ? next : job
      )))
    } catch (e) {
      setError(`取消编译失败：${(e as Error).message}`)
    } finally {
      setCancellingCompile(false)
    }
  }

  const handleRetryCompile = async (job: CompileResponse) => {
    if (!job.job_id || !job.retryable || compileRunning) return
    setRetryingJobId(job.job_id); setError('')
    try {
      const next = await retryCompileJob(job.job_id)
      setResult(next)
      setCompileJob(next.job_id ? next : null)
      await loadCompileHistory()
      if (!next.job_id || !isCompileJobActive(next.status)) await loadData()
    } catch (e) {
      setError(`重试编译失败：${(e as Error).message}`)
    } finally {
      setRetryingJobId(null)
    }
  }

  // 重编译过时/失败文档（recompile stale）
  const handleRecompileStale = async () => {
    if (staleCount === 0) {
      setRefreshMsg('当前没有需要重编译的过时文档')
      setTimeout(() => setRefreshMsg(''), 2000)
      return
    }
    setRecompiling(true); setError('')
    try {
      const res = await recompileStale(limit)
      setRefreshMsg(`已提交 ${res.queued} 个过时文档重编译`)
      await loadData()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setRecompiling(false)
      setTimeout(() => setRefreshMsg(''), 2000)
    }
  }

  const handlePromote = async (fileId: string) => {
    const file = allFiles.find((item) => item.id === fileId)
    const fileLabel = file?.title || fileId
    if (!window.confirm(`将“${fileLabel}”晋升到 wiki？系统会写入知识文件并更新 manifest 状态。`)) return

    setPromoting(true); setPromoteMsg('')
    try {
      const res = await promoteFile(fileId)
      setPromoteMsg(res.success ? `已晋升 ${fileId} 到 ${res.target}` : `晋升失败: ${res.message}`)
      await loadData()
    } catch (e) { setPromoteMsg('晋升失败: ' + (e as Error).message) }
    finally { setPromoting(false) }
  }

  const m = status?.manifests
  const qualityThreshold = status?.config?.min_quality_score ?? 85
  const selectedFilePromotable = (selectedFile?.quality_score ?? 0) >= qualityThreshold

  // Filter files for the compile view
  const filteredFiles = allFiles.filter((f) => {
    if (filter && f.status !== filter) return false
    if (search && !f.title.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const compiledFiles = allFiles.filter(f => f.status === 'compiled')
  const ingestedFiles = allFiles.filter(f => f.status === 'ingested')
  const compileRunning = Boolean(compileJob && isCompileJobActive(compileJob.status))
  const resultIsPositive = Boolean(
    result && !['failed', 'cancelled', 'interrupted', 'completed_with_errors'].includes(result.status),
  )
  const resultIsPartial = Boolean(result && result.status === 'completed_with_errors')

  const totalPages = Math.max(1, Math.ceil(filteredFiles.length / PAGE_SIZE))
  const pagedFiles = filteredFiles.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  const handleSearchChange = (value: string) => {
    setSearch(value)
    setPage(1)
  }

  const handleFilterChange = (value: string) => {
    setFilter(value)
    setPage(1)
  }

  const pageHeader = (
    <PageHeader title="编译控制" description="将源文件编译为结构化知识"
      actions={
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          {refreshMsg && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--status-success)', fontWeight: 500 }}>{refreshMsg}</span>}
          <button onClick={handleRefresh} disabled={refreshing}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '6px 12px', borderRadius: '4px', fontSize: 'var(--text-sm)', border: '1px solid var(--border-default)', background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer', fontWeight: 500, opacity: refreshing ? 0.5 : 1 }}>
            <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} /> 刷新
          </button>
        </div>
      }
    />
  )

  if (loadError) return (
    <div className="page-container" style={{ padding: 'var(--space-12) var(--space-10)', maxWidth: '100%', margin: '0 auto' }}>
      {pageHeader}
      <RequestErrorState error={loadError} onRetry={loadData} retrying={refreshing} />
    </div>
  )

  return (
    <div className="page-container" style={{ padding: 'var(--space-12) var(--space-10)', maxWidth: '100%', margin: '0 auto' }}>
      {pageHeader}

      {/* ── Stats Overview ── */}
      <SectionHeader title="编译概览" />
      <div className="grid-responsive-5" style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 'var(--space-4)', marginBottom: 'var(--space-10)' }}>
        <StatCard label="总计" value={m?.total ?? '-'} color="var(--color-primary)" icon={<FileText size={18} />} />
        <StatCard label="待编译" value={m?.ingested ?? '-'} color="var(--status-info)" icon={<Clock size={18} />} />
        <StatCard label="已编译" value={m?.compiled ?? '-'} color="var(--status-success)" icon={<FileCheck size={18} />} />
        <StatCard label="失败" value={m?.failed ?? '-'} color="var(--status-error)" icon={<AlertTriangle size={18} />} />
        <StatCard label="质量阈值" value={qualityThreshold} color="var(--status-warning)" />
      </div>

      {/* ── Compile Controls ── */}
      <SectionHeader title="编译参数" />
      <div style={{
        borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
        border: '1px solid var(--border-default)', marginBottom: 'var(--space-6)',
        background: 'var(--bg-card)', boxShadow: 'var(--shadow-sm)',
        display: 'flex', alignItems: 'flex-end', gap: 'var(--space-8)',
        flexWrap: 'wrap',
      }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 'var(--space-2)' }}>
            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', fontWeight: 400 }}>编译数量</span>
            <span style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--color-primary)' }}>{limit}</span>
          </div>
          <input type="range" min={1} max={100} value={limit} onChange={(e) => setLimit(+e.target.value)}
            style={{ width: '100%', accentColor: 'var(--color-primary)' }} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 'var(--space-2)' }}>
            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', fontWeight: 400 }}>并发数</span>
            <span style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--color-primary)' }}>{concurrency}</span>
          </div>
          <input type="range" min={1} max={5} value={concurrency} onChange={(e) => setConcurrency(+e.target.value)}
            style={{ width: '100%', accentColor: 'var(--color-primary)' }} />
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', cursor: 'pointer', fontWeight: 400, whiteSpace: 'nowrap', paddingBottom: '4px' }}>
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} style={{ width: '16px', height: '16px', accentColor: 'var(--color-primary)' }} />
          模拟运行
        </label>
        <button onClick={handleCompile} disabled={compiling || compileRunning || ingestedFiles.length === 0}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: '6px',
            padding: '8px 20px', borderRadius: '4px', fontSize: 'var(--text-sm)', fontWeight: 600,
            color: '#fff', background: 'var(--color-primary)', border: 'none', cursor: 'pointer',
            opacity: compiling || compileRunning || ingestedFiles.length === 0 ? 0.4 : 1,
            whiteSpace: 'nowrap',
          }}>
          {compiling || compileRunning ? <Loader2 size={14} className="animate-spin" /> : <PlayCircle size={14} />}
          {compiling ? '提交中...' : compileRunning ? '编译进行中...' : dryRun ? '模拟编译' : '开始编译'}
          {!compiling && !compileRunning && ingestedFiles.length > 0 && (
            <span style={{ fontSize: '12px', opacity: 0.8 }}>({ingestedFiles.length} 待编译)</span>
          )}
        </button>

        {/* 重编译过时文档 */}
        <button onClick={handleRecompileStale} disabled={recompiling || staleCount === 0}
          title={staleCount === 0 ? '当前没有需要重编译的过时文档' : `重新编译 ${staleCount} 个配置已过时的文档`}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: '6px',
            padding: '8px 20px', borderRadius: '4px', fontSize: 'var(--text-sm)', fontWeight: 600,
            color: 'var(--text-primary)', background: 'var(--bg-elevated)',
            border: '1px solid var(--border-default)', cursor: 'pointer',
            opacity: recompiling || staleCount === 0 ? 0.4 : 1, whiteSpace: 'nowrap',
          }}>
          {recompiling ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          {recompiling ? '提交中...' : '重编译过时'}
        </button>
      </div>

      {/* ── Compile Result ── */}
      {result && (
        <div style={{
          borderRadius: '4px', padding: 'var(--space-4)', marginBottom: 'var(--space-6)',
          background: resultIsPositive
            ? 'var(--status-success-bg)'
            : resultIsPartial ? 'var(--status-warning-bg)' : 'var(--status-error-bg)',
          border: `1px solid ${resultIsPositive
            ? 'var(--status-success-border)'
            : resultIsPartial ? 'var(--status-warning-border)' : 'var(--status-error-border)'}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-1)' }}>
            {resultIsPositive
              ? <CheckCircle2 size={14} style={{ color: 'var(--status-success)' }} />
              : resultIsPartial
                ? <AlertTriangle size={14} style={{ color: 'var(--status-warning)' }} />
                : <XCircle size={14} style={{ color: 'var(--status-error)' }} />}
            <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-primary)' }}>{result.message}</span>
          </div>
          {result.total > 0 && <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', margin: 0, fontWeight: 400 }}>总计 {result.total}，已处理 {result.processed}，成功 {result.compiled}，失败 {result.failed}</p>}
          {result.error && <p style={{ fontSize: 'var(--text-xs)', color: 'var(--status-error)', margin: 'var(--space-2) 0 0' }}>{result.error}</p>}
        </div>
      )}

      {error && <div style={{ borderRadius: '4px', padding: 'var(--space-4)', marginBottom: 'var(--space-6)', fontSize: 'var(--text-sm)', background: 'var(--status-error-bg)', color: 'var(--status-error)' }}>{error}</div>}

      {/* ── Compile Progress Bar ── */}
      {compileJob && compileRunning && (() => {
        const pct = compileJobPercent(compileJob)
        const cancelling = compileJob.status === 'cancelling' || compileJob.cancel_requested
        return (
          <div style={{
            borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
            border: '1px solid var(--color-primary)', marginBottom: 'var(--space-6)',
            background: 'var(--color-primary-bg)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-3)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <Loader2 size={16} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
                <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-primary)' }}>
                  {cancelling ? '正在取消编译' : '编译进行中'}
                </span>
              </div>
              <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-primary)' }}>
                {compileJob.processed} / {compileJob.total} ({pct}%)
              </span>
            </div>
            {/* 进度条 */}
            <div style={{
              height: '6px', borderRadius: 'var(--radius-full)',
              background: 'var(--bg-elevated)', overflow: 'hidden',
            }}>
              <div style={{
                height: '100%', borderRadius: 'var(--radius-full)',
                background: 'var(--color-primary)',
                width: `${pct}%`,
                transition: 'width 500ms ease-in-out',
              }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 'var(--space-2)' }}>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)' }}>
                <div>成功 {compileJob.compiled} · 失败 {compileJob.failed}</div>
                {compileJob.current_files.length > 0 && (
                  <div style={{ marginTop: '4px' }}>当前：{compileJob.current_files.join('、')}</div>
                )}
              </div>
              <button
                onClick={handleCancelCompile}
                disabled={cancellingCompile || cancelling}
                style={{
                  alignSelf: 'flex-start', padding: '4px 10px', borderRadius: '4px',
                  fontSize: 'var(--text-xs)', color: 'var(--status-error)',
                  background: 'var(--status-error-bg)', border: '1px solid var(--status-error-border)',
                  cursor: cancellingCompile || cancelling ? 'not-allowed' : 'pointer', fontWeight: 600,
                  opacity: cancellingCompile || cancelling ? 0.55 : 1,
                }}>
                {cancellingCompile || cancelling ? '取消中...' : '取消编译'}
              </button>
            </div>
          </div>
        )
      })()}

      {/* ── Compile Complete Summary ── */}
      {compileJob && !compileRunning && ['completed', 'completed_with_errors', 'failed', 'cancelled', 'interrupted'].includes(compileJob.status) && (() => {
        const partial = compileJob.status === 'completed_with_errors'
        const ok = compileJob.status === 'completed'
        const tone = partial ? 'warning' : ok ? 'success' : 'error'
        const toneColor = `var(--status-${tone})`
        const toneBg = `var(--status-${tone}-bg)`
        const toneBorder = `var(--status-${tone}-border)`
        const failedDocs = compileJob.failure_details?.length
          ? compileJob.failure_details
          : (compileJob.failed_files ?? []).map((srcId) => ({ src_id: srcId, error: '编译失败' }))
        return (
          <div style={{
            borderRadius: 'var(--radius-lg)', padding: 'var(--space-4) var(--space-5)',
            border: `1px solid ${toneBorder}`, marginBottom: 'var(--space-6)',
            background: toneBg,
            display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)',
          }}>
            {ok
              ? <CheckCircle2 size={18} style={{ color: toneColor, flexShrink: 0, marginTop: 2 }} />
              : partial
                ? <AlertTriangle size={18} style={{ color: toneColor, flexShrink: 0, marginTop: 2 }} />
                : <XCircle size={18} style={{ color: toneColor, flexShrink: 0, marginTop: 2 }} />}
            <div style={{ flex: 1, minWidth: 0 }}>
              <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: toneColor }}>
                {compileJob.message}：{compileJob.compiled} 个成功
                {compileJob.failed > 0 && `，${compileJob.failed} 个失败`}
              </span>
              {partial && failedDocs.length > 0 && (
                <ul style={{ margin: 'var(--space-2) 0 0', paddingInlineStart: '18px', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                  {failedDocs.slice(0, 10).map((f, i) => (
                    <li key={`${f.src_id}-${i}`} style={{ wordBreak: 'break-word' }}>
                      <span style={{ fontWeight: 600 }}>{f.src_id}</span>
                      {f.error && f.error !== '编译失败' && <>：{f.error}</>}
                    </li>
                  ))}
                  {failedDocs.length > 10 && <li>… 共 {failedDocs.length} 个失败文档</li>}
                </ul>
              )}
            </div>
            <button onClick={() => { setCompileJob(null); setResult(null) }}
              style={{ padding: '2px 6px', borderRadius: '4px', border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-dimmed)', fontSize: 'var(--text-xs)' }}>
              关闭
            </button>
          </div>
        )
      })()}

      {/* ── Durable Compile History ── */}
      <SectionHeader title="编译历史"
        action={<span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)' }}>保留于当前工作区</span>}
      />
      <div style={{
        border: '1px solid var(--border-default)', borderRadius: 'var(--radius-lg)',
        background: 'var(--bg-card)', marginBottom: 'var(--space-8)', overflow: 'hidden',
      }}>
        {compileHistory.length === 0 ? (
          <div style={{ padding: 'var(--space-6)', color: 'var(--text-muted)', fontSize: 'var(--text-sm)', textAlign: 'center' }}>
            尚无编译历史。提交任务后，即使服务重启也可在这里查看结果。
          </div>
        ) : compileHistory.map((job, index) => {
          const partial = job.status === 'completed_with_errors'
          const unsuccessful = ['failed', 'cancelled', 'interrupted'].includes(job.status)
          const busyRetry = retryingJobId === job.job_id
          return (
            <div key={job.job_id ?? `${job.created_at}-${index}`} style={{
              padding: 'var(--space-4) var(--space-5)',
              borderTop: index === 0 ? 'none' : '1px solid var(--border-subtle)',
              display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
              gap: 'var(--space-4)', flexWrap: 'wrap',
            }}>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                  <span style={{
                    fontSize: 'var(--text-xs)', fontWeight: 700,
                    color: unsuccessful
                      ? 'var(--status-error)'
                      : partial ? 'var(--status-warning)' : 'var(--status-success)',
                    background: unsuccessful
                      ? 'var(--status-error-bg)'
                      : partial ? 'var(--status-warning-bg)' : 'var(--status-success-bg)',
                    borderRadius: 'var(--radius-full)', padding: '2px 8px',
                  }}>
                    {JOB_STATUS_LABELS[job.status] ?? job.status}
                  </span>
                  {partial && (
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--status-warning)' }} title={(job.failed_files ?? []).join('、')}>
                      {job.compiled}/{job.total} 成功，失败：{(job.failed_files ?? []).slice(0, 3).join('、') || `${job.failed} 个`}{(job.failed_files?.length ?? 0) > 3 ? ' …' : ''}
                    </span>
                  )}
                  <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)', fontWeight: 600 }}>
                    {job.compiled}/{job.total} 成功 · 第 {job.attempt} 次尝试
                  </span>
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)' }}>
                    {formatJobTime(job.finished_at ?? job.started_at ?? job.created_at)}
                  </span>
                </div>
                <div style={{ marginTop: 'var(--space-2)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                  并发 {job.concurrency} · 限制 {job.limit ?? '全部'}
                  {job.retry_of && <> · 重试自 {job.retry_of.slice(0, 8)}</>}
                  {job.job_id && <> · ID {job.job_id.slice(0, 8)}</>}
                </div>
                {job.error && (
                  <div style={{ marginTop: 'var(--space-2)', fontSize: 'var(--text-xs)', color: 'var(--status-error)', wordBreak: 'break-word' }}>
                    {job.error}
                  </div>
                )}
              </div>
              {job.retryable && job.job_id && (
                <button
                  onClick={() => { void handleRetryCompile(job) }}
                  disabled={busyRetry || compileRunning}
                  aria-label={`重试编译任务 ${job.job_id.slice(0, 8)}`}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: '6px',
                    padding: '6px 10px', borderRadius: '4px', fontSize: 'var(--text-xs)',
                    color: 'var(--color-primary)', background: 'var(--color-primary-bg)',
                    border: '1px solid var(--color-primary)', fontWeight: 600,
                    cursor: busyRetry || compileRunning ? 'not-allowed' : 'pointer',
                    opacity: busyRetry || compileRunning ? 0.5 : 1,
                  }}>
                  {busyRetry ? <Loader2 size={12} className="animate-spin" /> : <RotateCcw size={12} />}
                  {busyRetry ? '重试提交中...' : '重试任务'}
                </button>
              )}
            </div>
          )
        })}
      </div>

      {/* ── File List ── */}
      <SectionHeader title={`文件列表 (${filteredFiles.length})`}
        action={
          compiledFiles.length > 0 ? (
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--status-success)', fontWeight: 500 }}>
              {compiledFiles.length} 已编译
            </span>
          ) : undefined
        }
      />

      {/* Search & Filter */}
      <div className="search-filter-bar" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <Search size={15} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dimmed)' }} />
          <input style={{
            width: '100%', padding: '6px 10px 6px 32px', borderRadius: '4px',
            fontSize: 'var(--text-sm)', border: '1px solid var(--border-default)',
            background: 'var(--bg-input)', color: 'var(--text-primary)', outline: 'none', lineHeight: 1.5,
          }} placeholder="搜索文件名..." value={search} onChange={(e) => handleSearchChange(e.target.value)} />
        </div>
        <select style={{
          padding: '6px 10px', borderRadius: '4px', fontSize: 'var(--text-sm)',
          border: '1px solid var(--border-default)', background: 'var(--bg-input)',
          color: 'var(--text-primary)', outline: 'none', cursor: 'pointer',
        }} value={filter} onChange={(e) => handleFilterChange(e.target.value)}>
          <option value="">全部状态</option>
          <option value="ingested">待编译</option>
          <option value="compiled">已编译</option>
          <option value="failed">失败</option>
          <option value="promoted">已晋升</option>
          <option value="promoted_to_wiki">Wiki</option>
        </select>
      </div>

      {/* File Table */}
      {filteredFiles.length > 0 ? (
        <div className="table-scroll" style={{ borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-default)', overflow: 'hidden', marginBottom: 'var(--space-6)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--bg-elevated)' }}>
                {['文件名', '类型', '状态', '大小', '质量分', '操作'].map((h) => (
                  <th key={h} style={{
                    textAlign: 'left', padding: '8px 16px',
                    fontSize: 'var(--text-xs)', fontWeight: 600,
                    color: 'var(--text-dimmed)',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pagedFiles.map((f) => {
                const sc = STATUS_COLORS[f.status] || { color: 'var(--text-muted)', bg: 'var(--bg-elevated)' }
                const promotable = (f.quality_score ?? 0) >= qualityThreshold
                return (
                  <tr key={f.id} style={{ borderTop: '1px solid var(--border-subtle)', cursor: 'pointer' }}
                    onClick={() => setSelectedFile(f)}
                    onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
                    <td style={{ padding: '8px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <FileText size={15} style={{ color: 'var(--text-dimmed)', flexShrink: 0 }} />
                        <span style={{ fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.title}</span>
                      </div>
                    </td>
                    <td style={{ padding: '8px 16px', fontSize: 'var(--text-sm)', color: 'var(--text-muted)', fontWeight: 400 }}>{f.type}</td>
                    <td style={{ padding: '8px 16px' }}>
                      <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '2px 8px',
                        borderRadius: 'var(--radius-full)',
                        fontSize: 'var(--text-xs)', fontWeight: 600, letterSpacing: '0.125px',
                        background: sc.bg, color: sc.color,
                      }}>
                        {f.status === 'compiling' && <Loader2 size={10} className="animate-spin" />}
                        {statusLabel(f.status)}
                      </span>
                    </td>
                    <td style={{ padding: '8px 16px', fontSize: 'var(--text-sm)', color: 'var(--text-muted)', fontWeight: 400 }}>{formatBytes(f.size_bytes)}</td>
                    <td style={{
                      padding: '8px 16px', fontSize: 'var(--text-sm)', fontWeight: 600,
                      color: promotable ? 'var(--status-success)' : (f.quality_score ?? 0) >= 60 ? 'var(--status-warning)' : 'var(--text-dimmed)',
                    }}>
                      {f.quality_score ?? '-'}
                    </td>
                    <td style={{ padding: '8px 16px' }} onClick={(e) => e.stopPropagation()}>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        {(f.status === 'compiled' || f.status === 'promoted_to_wiki') && (
                          <button onClick={() => setSelectedFile(f)} title="查看详情"
                            style={{ padding: '4px 6px', borderRadius: '4px', border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-dimmed)' }}>
                            <ChevronRight size={14} />
                          </button>
                        )}
                        {f.status === 'compiled' && (
                          <button
                            onClick={() => handlePromote(f.id)}
                            disabled={promoting || !promotable}
                            aria-label={promotable ? `晋升 ${f.title} 到 Wiki` : `${f.title} 未达到质量门槛 ${qualityThreshold}`}
                            title={promotable ? '晋升到 Wiki' : `质量分 ${f.quality_score ?? 0}，低于晋升门槛 ${qualityThreshold}`}
                            style={{
                              padding: '4px 6px', borderRadius: '4px', border: 'none', background: 'transparent',
                              cursor: promotable ? 'pointer' : 'not-allowed',
                              color: promotable ? 'var(--color-primary)' : 'var(--text-dimmed)',
                              opacity: promoting || !promotable ? 0.45 : 1,
                            }}>
                            <ArrowUpRight size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-default)', padding: 'var(--space-10)', textAlign: 'center', marginBottom: 'var(--space-6)' }}>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>暂无文件，请先在文件管理页面上传文件</p>
        </div>
      )}

      {promoteMsg && (
        <div style={{
          borderRadius: '4px', padding: 'var(--space-3) var(--space-4)', marginBottom: 'var(--space-5)',
          fontSize: 'var(--text-sm)', fontWeight: 500,
          background: promoteMsg.startsWith('晋升失败') ? 'var(--status-error-bg)' : 'var(--status-success-bg)',
          color: promoteMsg.startsWith('晋升失败') ? 'var(--status-error)' : 'var(--status-success)',
        }}>{promoteMsg}</div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: 'var(--space-3) 0', marginBottom: 'var(--space-4)',
        }}>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)' }}>
            共 {filteredFiles.length} 个文件，第 {page}/{totalPages} 页
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)' }}>
            <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1}
              style={{ padding: '4px 8px', borderRadius: '4px', border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)', opacity: page <= 1 ? 0.3 : 1 }}>
              <ChevronLeft size={14} />
            </button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const p = Math.max(1, Math.min(page - 2, totalPages - 4)) + i
              if (p > totalPages) return null
              return (
                <button key={p} onClick={() => setPage(p)}
                  style={{
                    padding: '4px 10px', borderRadius: '4px', border: 'none',
                    fontSize: 'var(--text-xs)', fontWeight: p === page ? 600 : 400,
                    cursor: 'pointer',
                    background: p === page ? 'var(--color-primary-bg)' : 'transparent',
                    color: p === page ? 'var(--color-primary)' : 'var(--text-muted)',
                  }}>
                  {p}
                </button>
              )
            })}
            <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page >= totalPages}
              style={{ padding: '4px 8px', borderRadius: '4px', border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)', opacity: page >= totalPages ? 0.3 : 1 }}>
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}

      {/* ── File Detail Modal ── */}
      {selectedFile && (
        <ErrorBoundary fallback={
          <div style={{
            position: 'fixed', inset: 0, zIndex: 50,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(0,0,0,0.32)',
          }} onClick={() => setSelectedFile(null)}>
            <div style={{
              padding: '24px', borderRadius: '12px', background: '#fff',
              maxWidth: '400px', textAlign: 'center',
            }}>
              <p style={{ fontSize: 'var(--text-sm)', color: 'var(--status-error)', marginBottom: '16px' }}>
                文件详情渲染出错
              </p>
              <button onClick={() => setSelectedFile(null)}
                style={{ padding: '8px 16px', borderRadius: '4px', background: '#0075de', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
                关闭
              </button>
            </div>
          </div>
        }>
        <div style={{
          position: 'fixed', inset: 0, zIndex: 50,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'var(--bg-overlay)',
        }} onClick={() => { setSelectedFile(null); setPromoteMsg('') }}>
          <div style={{
            width: '100%', maxWidth: '560px', maxHeight: '85vh',
            borderRadius: 'var(--radius-lg)', padding: 'var(--space-6)',
            background: 'var(--bg-card)', boxShadow: 'var(--shadow-lg)',
            overflow: 'auto',
          }} onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 'var(--space-5)' }}>
              <div>
                <h3 style={{
                  fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)',
                  margin: 0, letterSpacing: '-0.25px',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '400px',
                }}>{selectedFile.title}</h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
                  {(() => {
                    const sc = STATUS_COLORS[selectedFile.status] || { color: 'var(--text-muted)', bg: 'var(--bg-elevated)' }
                    return (
                      <span style={{
                        display: 'inline-flex', padding: '2px 8px',
                        borderRadius: 'var(--radius-full)',
                        fontSize: 'var(--text-xs)', fontWeight: 600, letterSpacing: '0.125px',
                        background: sc.bg, color: sc.color,
                      }}>{statusLabel(selectedFile.status)}</span>
                    )
                  })()}
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)' }}>{selectedFile.id}</span>
                </div>
              </div>
              <button onClick={() => { setSelectedFile(null); setPromoteMsg('') }}
                style={{ padding: '4px', borderRadius: '4px', border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-dimmed)', flexShrink: 0 }}>
                ✕
              </button>
            </div>

            {/* Metadata Grid */}
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-3)',
              padding: 'var(--space-4)', borderRadius: 'var(--radius-lg)',
              background: 'var(--bg-elevated)', marginBottom: 'var(--space-5)',
            }}>
              {[
                { label: '类型', value: selectedFile.type },
                { label: '大小', value: formatBytes(selectedFile.size_bytes) },
                { label: '质量分', value: String(selectedFile.quality_score ?? '-'), highlight: true },
              ].map((item) => (
                <div key={item.label}>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', fontWeight: 600, marginBottom: '2px' }}>{item.label}</div>
                  <div style={{
                    fontSize: 'var(--text-sm)', fontWeight: 600,
                    color: item.highlight
                      ? selectedFilePromotable ? 'var(--status-success)' : (selectedFile.quality_score ?? 0) >= 60 ? 'var(--status-warning)' : 'var(--text-dimmed)'
                      : 'var(--text-primary)',
                  }}>{item.value}</div>
                </div>
              ))}
            </div>

            {/* Provenance Label (Layer 0) */}
            {selectedFile.compiled_summary?.provenance && (() => {
              const prov = selectedFile.compiled_summary!.provenance!
              const PROV_STYLES: Record<string, { color: string; bg: string; icon: React.ReactNode; label: string }> = {
                extracted: { color: 'var(--status-success)', bg: 'var(--status-success-bg)', icon: <ShieldCheck size={13} />, label: '直接提取' },
                merged: { color: 'var(--color-primary)', bg: 'var(--color-primary-bg)', icon: <Shield size={13} />, label: '合并重组' },
                inferred: { color: 'var(--status-warning)', bg: 'var(--status-warning-bg)', icon: <ShieldQuestion size={13} />, label: '推断补充' },
                ambiguous: { color: 'var(--status-error)', bg: 'var(--status-error-bg)', icon: <ShieldAlert size={13} />, label: '来源不明' },
              }
              const style = PROV_STYLES[prov.overall_label] || PROV_STYLES.ambiguous
              return (
                <div style={{
                  padding: 'var(--space-3) var(--space-4)', marginBottom: 'var(--space-4)', borderRadius: '4px',
                  background: style.bg, border: `1px solid ${style.color}33`,
                  display: 'flex', alignItems: 'center', gap: 'var(--space-3)',
                }}>
                  <span style={{ color: style.color, display: 'flex', alignItems: 'center' }}>{style.icon}</span>
                  <div>
                    <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: style.color }}>
                      溯源: {style.label}
                    </span>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', marginLeft: '8px' }}>
                      置信度 {(prov.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              )
            })()}

            {/* Lint Results (Layer 1) */}
            {selectedFile.compiled_summary?.lint && (() => {
              const lint = selectedFile.compiled_summary!.lint!
              return (
                <div style={{
                  padding: 'var(--space-3) var(--space-4)', marginBottom: 'var(--space-4)', borderRadius: '4px',
                  background: lint.passed ? 'var(--status-success-bg)' : 'var(--status-warning-bg)',
                  border: `1px solid ${lint.passed ? 'var(--status-success)' : 'var(--status-warning)'}33`,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: lint.issues.length > 0 ? 'var(--space-2)' : 0 }}>
                    {lint.passed
                      ? <CheckCircle2 size={13} style={{ color: 'var(--status-success)' }} />
                      : <AlertTriangle size={13} style={{ color: 'var(--status-warning)' }} />}
                    <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: lint.passed ? 'var(--status-success)' : 'var(--status-warning)' }}>
                      Lint {lint.passed ? '通过' : `未通过 (${lint.error_count} 错误, ${lint.warning_count} 警告)`}
                    </span>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', marginLeft: '4px' }}>
                      完整度 {(lint.score * 100).toFixed(0)}%
                    </span>
                  </div>
                  {lint.issues.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                      {lint.issues.slice(0, 5).map((issue, i) => (
                        <div key={i} style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', display: 'flex', gap: '4px' }}>
                          <span style={{
                            fontWeight: 600,
                            color: issue.severity === 'error' ? 'var(--status-error)' : issue.severity === 'warning' ? 'var(--status-warning)' : 'var(--text-dimmed)',
                          }}>
                            {issue.severity === 'error' ? 'E' : issue.severity === 'warning' ? 'W' : 'I'}
                          </span>
                          <span>{issue.message}</span>
                        </div>
                      ))}
                      {lint.issues.length > 5 && (
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)' }}>
                          ...还有 {lint.issues.length - 5} 个问题
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )
            })()}

            {/* Error Message */}
            {selectedFile.error_message && typeof selectedFile.error_message === 'string' && (
              <div style={{
                padding: 'var(--space-4)', marginBottom: 'var(--space-5)', borderRadius: '4px',
                background: 'var(--status-error-bg)', border: '1px solid var(--status-error-border)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-1)' }}>
                  <AlertTriangle size={13} style={{ color: 'var(--status-error)' }} />
                  <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--status-error)' }}>编译错误</span>
                </div>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--status-error)', margin: 0, fontWeight: 400, lineHeight: 'var(--leading-relaxed)' }}>{selectedFile.error_message}</p>
              </div>
            )}

            {/* Compilation Summary */}
            {selectedFile.compiled_summary && (
              <div style={{ marginBottom: 'var(--space-5)' }}>
                {/* One-line Summary */}
                {selectedFile.compiled_summary.one_line && (
                  <div style={{ marginBottom: 'var(--space-4)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
                      <FileText size={13} style={{ color: 'var(--text-dimmed)' }} />
                      <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-dimmed)' }}>摘要</span>
                    </div>
                    <p style={{ fontSize: 'var(--text-sm)', lineHeight: 'var(--leading-relaxed)', color: 'var(--text-primary)', fontWeight: 400, margin: 0 }}>
                      {selectedFile.compiled_summary.one_line}
                    </p>
                  </div>
                )}

                {/* Key Points */}
                {Array.isArray(selectedFile.compiled_summary.key_points) && selectedFile.compiled_summary.key_points.length > 0 && (
                  <div style={{ marginBottom: 'var(--space-4)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
                      <ChevronDown size={13} style={{ color: 'var(--text-dimmed)' }} />
                      <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-dimmed)' }}>关键要点</span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                      {selectedFile.compiled_summary.key_points.slice(0, 10).map((point: string, i: number) => (
                        <div key={i} style={{ display: 'flex', gap: 'var(--space-2)', fontSize: 'var(--text-sm)', lineHeight: 'var(--leading-relaxed)' }}>
                          <span style={{ color: 'var(--color-primary)', fontWeight: 600, flexShrink: 0 }}>{i + 1}.</span>
                          <span style={{ color: 'var(--text-secondary)', fontWeight: 400 }}>{point}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Concepts */}
                {Array.isArray(selectedFile.compiled_summary.concepts) && selectedFile.compiled_summary.concepts.length > 0 && (
                  <div style={{ marginBottom: 'var(--space-4)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
                      <Tag size={13} style={{ color: 'var(--text-dimmed)' }} />
                      <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-dimmed)' }}>提取概念</span>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)' }}>
                      {selectedFile.compiled_summary.concepts.slice(0, 20).map((concept: Record<string, string> | string, i: number) => {
                        const label = typeof concept === 'string' ? concept : (concept.name || concept.title || JSON.stringify(concept))
                        return (
                          <span key={i} style={{
                            padding: '3px 10px', borderRadius: 'var(--radius-full)',
                            fontSize: 'var(--text-xs)', background: 'var(--status-success-bg)',
                            color: 'var(--status-success)', fontWeight: 500,
                          }}>{label}</span>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Detailed Summary (collapsible, truncated) */}
                {selectedFile.compiled_summary.detailed_summary && (
                  <details style={{ marginBottom: 'var(--space-3)' }}>
                    <summary style={{
                      fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-dimmed)',
                      cursor: 'pointer', marginBottom: 'var(--space-2)',
                      display: 'flex', alignItems: 'center', gap: 'var(--space-1)',
                    }}>
                      <ChevronRight size={12} /> 详细摘要
                    </summary>
                    <p style={{
                      fontSize: 'var(--text-sm)', lineHeight: 'var(--leading-relaxed)',
                      color: 'var(--text-secondary)', fontWeight: 400, margin: 0,
                      padding: 'var(--space-3)', background: 'var(--bg-elevated)',
                      borderRadius: 'var(--radius-lg)',
                      maxHeight: '300px', overflow: 'auto',
                    }}>
                      {selectedFile.compiled_summary.detailed_summary.length > 3000
                        ? selectedFile.compiled_summary.detailed_summary.slice(0, 3000) + '...'
                        : selectedFile.compiled_summary.detailed_summary}
                    </p>
                  </details>
                )}
              </div>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: 'var(--space-2)', borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-4)' }}>
              {selectedFile.status === 'compiled' && (
                <>
                  <button
                    onClick={() => handlePromote(selectedFile.id)}
                    disabled={promoting || !selectedFilePromotable}
                    title={selectedFilePromotable ? '晋升到 Wiki' : `质量分 ${selectedFile.quality_score ?? 0}，低于晋升门槛 ${qualityThreshold}`}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: '6px',
                      padding: '8px 16px', borderRadius: '4px', fontSize: 'var(--text-sm)', fontWeight: 600,
                      color: selectedFilePromotable ? '#fff' : 'var(--text-dimmed)',
                      background: selectedFilePromotable ? 'var(--color-primary)' : 'var(--bg-elevated)',
                      border: 'none', cursor: selectedFilePromotable ? 'pointer' : 'not-allowed',
                      opacity: promoting ? 0.5 : 1,
                    }}>
                    {promoting ? <Loader2 size={14} className="animate-spin" /> : <ArrowUpRight size={14} />}
                    晋升到 Wiki
                  </button>
                  {!selectedFilePromotable && (
                    <span role="note" style={{ alignSelf: 'center', fontSize: 'var(--text-xs)', color: 'var(--status-warning)' }}>
                      当前质量分 {selectedFile.quality_score ?? 0}，需达到 {qualityThreshold}
                    </span>
                  )}
                </>
              )}
              {selectedFile.status === 'failed' && (
                <div style={{
                  padding: 'var(--space-3)', borderRadius: '4px', fontSize: 'var(--text-sm)',
                  background: 'var(--status-info-bg)', color: 'var(--status-info)', fontWeight: 500,
                }}>
                  <RotateCcw size={13} style={{ marginRight: '6px', verticalAlign: 'middle' }} />
                  使用上方编译按钮重新编译失败文件
                </div>
              )}
            </div>
          </div>
        </div>
        </ErrorBoundary>
      )}
    </div>
  )
}
