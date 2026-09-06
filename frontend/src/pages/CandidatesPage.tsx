import { useEffect, useState, useCallback } from 'react'
import { RefreshCw, CheckCircle2, XCircle, AlertTriangle, MessageSquare } from 'lucide-react'
import { getCandidates, getCandidateDetail, promoteCandidate, discardCandidate } from '@/lib/api'
import type { CandidateDetail, CandidateMeta } from '@/lib/api'
import { classifyRequestError, type RequestErrorInfo } from '@/lib/errors'
import { withMinDelay } from '@/lib/utils'
import PageHeader from '@/components/ui/PageHeader'
import EmptyState from '@/components/ui/EmptyState'
import RequestErrorState from '@/components/ui/RequestErrorState'

const STATUS_META: Record<string, { color: string; label: string }> = {
  candidate: { color: 'var(--status-info)', label: '待审核' },
  promoted: { color: 'var(--status-success)', label: '已晋升' },
  discarded: { color: 'var(--text-dimmed)', label: '已丢弃' },
}

export default function CandidatesPage() {
  const [candidates, setCandidates] = useState<CandidateMeta[]>([])
  const [filter, setFilter] = useState<'candidate' | 'promoted' | 'discarded' | 'all'>('candidate')
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')
  const [loadError, setLoadError] = useState<RequestErrorInfo | null>(null)
  const [detail, setDetail] = useState<CandidateDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // UX-03：展开候选详情（全文/来源/冲突/晋升 diff）
  const openDetail = useCallback(async (id: string) => {
    if (detail?.id === id) { setDetail(null); return }
    setDetailLoading(true); setDetail(null)
    try {
      setDetail(await getCandidateDetail(id))
    } catch (e) {
      setMsg((e as Error).message)
      setTimeout(() => setMsg(''), 2500)
    } finally {
      setDetailLoading(false)
    }
  }, [detail])

  const loadCandidates = useCallback(async (isCancelled: () => boolean = () => false) => {
    try {
      const status = filter === 'all' ? undefined : filter
      const res = await withMinDelay(getCandidates(status as 'candidate' | 'promoted' | 'discarded'))
      if (isCancelled()) return
      setCandidates(res.candidates)
      setLoadError(null)
    } catch (e) {
      if (!isCancelled()) setLoadError(classifyRequestError(e))
    } finally {
      if (!isCancelled()) setLoading(false)
    }
  }, [filter])

  const load = useCallback(async () => {
    setLoading(true)
    await loadCandidates()
  }, [loadCandidates])

  useEffect(() => {
    let cancelled = false
    queueMicrotask(() => {
      void loadCandidates(() => cancelled)
    })
    return () => { cancelled = true }
  }, [loadCandidates])

  const handlePromote = async (id: string) => {
    const candidate = candidates.find((item) => item.id === id)
    const candidateLabel = candidate?.query || candidate?.title || id
    if (!window.confirm(`将“${candidateLabel}”写入 wiki 摘要和概念文件，并把候选状态改为已晋升？`)) return

    try {
      const res = await promoteCandidate(id)
      setMsg(res.success ? `已晋升 ${id}` : `失败: ${res.reason}`)
      await load()
    } catch (e) {
      setMsg((e as Error).message)
    }
    setTimeout(() => setMsg(''), 2000)
  }

  const handleDiscard = async (id: string) => {
    const candidate = candidates.find((item) => item.id === id)
    const candidateLabel = candidate?.query || candidate?.title || id
    if (!window.confirm(`丢弃“${candidateLabel}”？候选内容文件会被永久删除，元数据将保留为已丢弃状态。`)) return

    try {
      const res = await discardCandidate(id)
      setMsg(res.success ? `已丢弃 ${id}` : `失败: ${res.reason}`)
      await load()
    } catch (e) {
      setMsg((e as Error).message)
    }
    setTimeout(() => setMsg(''), 2000)
  }

  const pageHeader = (
    <PageHeader
      title="候选知识管理"
      description="管理 Query-as-Contribution 生成的候选知识（查看 / 确认 / 丢弃）"
      actions={(
        <button onClick={load} disabled={loading}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '6px 12px',
            borderRadius: '4px', fontSize: 'var(--text-sm)', border: '1px solid var(--border-default)',
            background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer',
            opacity: loading ? 0.5 : 1 }}>
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> 刷新
        </button>
      )}
    />
  )

  if (loadError) return (
    <>
      {pageHeader}
      <RequestErrorState error={loadError} onRetry={load} retrying={loading} />
    </>
  )

  return (
    <>
      {pageHeader}

      {msg && (
        <div style={{ padding: '8px 12px', marginBottom: '12px', borderRadius: '4px',
          background: 'var(--bg-elevated)', fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
          {msg}
        </div>
      )}

      {/* 过滤器 */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
        {(['candidate', 'promoted', 'discarded', 'all'] as const).map(f => (
          <button key={f} onClick={() => { setFilter(f); setLoading(true) }}
            style={{
              padding: '4px 12px', borderRadius: '4px', fontSize: 'var(--text-sm)', fontWeight: 500,
              border: '1px solid', cursor: 'pointer',
              borderColor: filter === f ? 'var(--color-primary)' : 'var(--border-default)',
              background: filter === f ? 'var(--color-primary-bg)' : 'transparent',
              color: filter === f ? 'var(--color-primary)' : 'var(--text-muted)',
            }}>
            {f === 'all' ? '全部' : STATUS_META[f].label}
          </button>
        ))}
      </div>

      {candidates.length === 0 ? (
        <EmptyState
          icon={<MessageSquare size={28} />}
          title="暂无候选知识"
          description="启用查询页的'贡献模式'后，高质量回答会写入候选区"
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {candidates.map(c => (
            <div key={c.id}
              style={{
                padding: '14px 16px', borderRadius: '8px', border: '1px solid var(--border-default)',
                background: 'var(--bg-card)',
              }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                    <MessageSquare size={14} style={{ color: 'var(--color-primary)' }} />
                    <button onClick={() => { void openDetail(c.id) }}
                      title="查看全文 / 来源 / 冲突 / 晋升 diff"
                      style={{ fontWeight: 600, color: 'var(--text-primary)', background: 'transparent',
                        border: 'none', padding: 0, cursor: 'pointer', fontSize: 'inherit' }}>
                      {c.query || c.title}
                    </button>
                    <span style={{ fontSize: 'var(--text-xs)', padding: '2px 6px', borderRadius: '4px',
                      color: STATUS_META[c.status]?.color, background: 'var(--bg-elevated)' }}>
                      {STATUS_META[c.status]?.label || c.status}
                    </span>
                    {c.needs_review && (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '2px',
                        fontSize: 'var(--text-xs)', color: 'var(--status-warning)' }}>
                        <AlertTriangle size={11} /> 需审核
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', marginBottom: '4px' }}>
                    {c.id} · 质量 <span style={{ color: c.quality_score >= 80 ? 'var(--status-success)' : c.quality_score >= 60 ? 'var(--status-warning)' : 'var(--status-error)' }}>{c.quality_score}</span>
                    {c.source_manifest_ids?.length ? ` · 来源 ${c.source_manifest_ids.join(', ')}` : ''}
                  </div>
                  {c.answer && (
                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)',
                      maxHeight: '60px', overflow: 'hidden' }}>
                      {(c.answer || '').slice(0, 120)}{(c.answer || '').length > 120 ? '...' : ''}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  {c.status === 'candidate' && (
                    <>
                      <button onClick={(e) => { e.stopPropagation(); handlePromote(c.id) }}
                        style={{ padding: '4px 10px', borderRadius: '4px', fontSize: 'var(--text-xs)',
                          border: '1px solid var(--status-success)', background: 'var(--status-success-bg)',
                          color: 'var(--status-success)', cursor: 'pointer' }}>
                        <CheckCircle2 size={12} /> 确认
                      </button>
                      <button onClick={(e) => { e.stopPropagation(); handleDiscard(c.id) }}
                        style={{ padding: '4px 10px', borderRadius: '4px', fontSize: 'var(--text-xs)',
                          border: '1px solid var(--border-default)', background: 'transparent',
                          color: 'var(--text-dimmed)', cursor: 'pointer' }}>
                        <XCircle size={12} /> 丢弃
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* UX-03：候选详情（全文 / 来源 / 冲突 / 晋升 diff） */}
              {detailLoading && detail?.id !== c.id && (
                <div style={{ marginTop: '10px', fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)' }}>
                  加载详情…
                </div>
              )}
              {detail?.id === c.id && (
                <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid var(--border-subtle)' }}>
                  {detail.contradiction && (detail.contradiction as { has_contradiction?: boolean }).has_contradiction && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px',
                      fontSize: 'var(--text-xs)', color: 'var(--status-warning)' }}>
                      <AlertTriangle size={12} />
                      检测到与现有知识可能矛盾：
                      {(detail.contradiction as { conflicts?: Array<{ summary?: string }> }).conflicts?.map((c2, i2, arr) => (
                        <span key={i2}>{c2?.summary || '未知冲突'}{i2 < arr.length - 1 ? '；' : ''}</span>
                      ))}
                    </div>
                  )}
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', marginBottom: '6px' }}>
                    来源：{(detail.source_manifest_ids?.length ? detail.source_manifest_ids.join('、') : '无 manifest 关联')}
                    {detail.file ? ` · 文件 ${detail.file}` : ''}
                  </div>
                  <pre style={{ margin: '0 0 10px', padding: '10px 12px', borderRadius: '6px',
                    background: 'var(--bg-elevated)', fontSize: 'var(--text-xs)', lineHeight: 1.6,
                    color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                    maxHeight: '260px', overflow: 'auto' }}>
                    {detail.full_text || detail.answer_preview || '（无内容）'}
                  </pre>
                  {detail.status === 'candidate' && detail.promote_plan && (
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                      <div style={{ fontWeight: 600, marginBottom: '4px' }}>确认后将写入（最终 diff）：</div>
                      {detail.promote_plan.blockers?.length > 0 && (
                        <div style={{ color: 'var(--status-error)', marginBottom: '4px' }}>
                          阻塞：{detail.promote_plan.blockers.join('；')}
                        </div>
                      )}
                      <ul style={{ margin: 0, paddingInlineStart: '18px' }}>
                        {detail.promote_plan.changes.map((change) => (
                          <li key={change.path}>
                            <span style={{
                              color: change.action === 'overwrite' ? 'var(--status-warning)' : 'var(--status-success)',
                              fontWeight: 600,
                            }}>
                              {change.action === 'overwrite' ? '覆盖' : change.action === 'identical' ? '相同' : '新增'}
                            </span>
                            {' '}{change.path}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  )
}
