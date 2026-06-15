import { useEffect, useState, useCallback } from 'react'
import { RefreshCw, CheckCircle2, XCircle, AlertTriangle, MessageSquare } from 'lucide-react'
import { getCandidates, promoteCandidate, discardCandidate } from '@/lib/api'
import type { CandidateMeta } from '@/lib/api'
import { withMinDelay, qualityColor } from '@/lib/utils'
import PageHeader from '@/components/ui/PageHeader'
import EmptyState from '@/components/ui/EmptyState'

const STATUS_META: Record<string, { color: string; label: string }> = {
  candidate: { color: 'var(--status-info)', label: '待审核' },
  promoted: { color: 'var(--status-success)', label: '已晋升' },
  discarded: { color: 'var(--text-dimmed)', label: '已丢弃' },
}

export default function CandidatesPage() {
  const [candidates, setCandidates] = useState<CandidateMeta[]>([])
  const [filter, setFilter] = useState<'candidate' | 'promoted' | 'discarded' | 'all'>('candidate')
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState('')
  const [, setSelected] = useState<CandidateMeta | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const status = filter === 'all' ? undefined : filter
      const res = await withMinDelay(getCandidates(status as 'candidate' | 'promoted' | 'discarded'))
      setCandidates(res.candidates)
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => { load() }, [load])

  const handlePromote = async (id: string) => {
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
    try {
      const res = await discardCandidate(id)
      setMsg(res.success ? `已丢弃 ${id}` : `失败: ${res.reason}`)
      await load()
    } catch (e) {
      setMsg((e as Error).message)
    }
    setTimeout(() => setMsg(''), 2000)
  }

  return (
    <>
      <PageHeader
        title="候选知识管理"
        description="管理 Query-as-Contribution 生成的候选知识（查看 / 确认 / 丢弃）"
        actions={
          <button onClick={load} disabled={loading}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '6px 12px',
              borderRadius: '4px', fontSize: 'var(--text-sm)', border: '1px solid var(--border-default)',
              background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer',
              opacity: loading ? 0.5 : 1 }}>
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> 刷新
          </button>
        }
      />

      {msg && (
        <div style={{ padding: '8px 12px', marginBottom: '12px', borderRadius: '4px',
          background: 'var(--bg-elevated)', fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
          {msg}
        </div>
      )}

      {/* 过滤器 */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
        {(['candidate', 'promoted', 'discarded', 'all'] as const).map(f => (
          <button key={f} onClick={() => setFilter(f)}
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
          icon="📝"
          title="暂无候选知识"
          description="启用查询页的'贡献模式'后，高质量回答会写入候选区"
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {candidates.map(c => (
            <div key={c.id}
              onClick={() => setSelected(c)}
              style={{
                padding: '14px 16px', borderRadius: '8px', border: '1px solid var(--border-default)',
                background: 'var(--bg-card)', cursor: 'pointer',
              }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                    <MessageSquare size={14} style={{ color: 'var(--color-primary)' }} />
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{c.query || c.title}</span>
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
                    {c.id} · 质量 <span className={qualityColor(c.quality_score)}>{c.quality_score}</span>
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
            </div>
          ))}
        </div>
      )}
    </>
  )
}
