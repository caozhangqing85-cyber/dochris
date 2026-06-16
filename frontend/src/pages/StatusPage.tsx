import { useEffect, useState, useCallback } from 'react'
import { RefreshCw } from 'lucide-react'
import { getStatus } from '@/lib/api'
import { withMinDelay } from '@/lib/utils'
import type { StatusResponse } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import SectionHeader from '@/components/ui/SectionHeader'

// Row 提到组件外，避免每次父渲染重建组件类型导致子树重挂（React 反模式）
function Row({ label, value, monospace }: { label: string; value: string; monospace?: boolean }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '12px 0', borderBottom: '1px solid var(--border-subtle)',
    }}>
      <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>{label}</span>
      <span style={{
        fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--text-primary)',
        fontFamily: monospace ? 'var(--font-mono)' : 'inherit',
        maxWidth: '60%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        textAlign: 'right',
      }}>{value}</span>
    </div>
  )
}

export default function StatusPage() {
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshMsg, setRefreshMsg] = useState('')
  const load = useCallback(async () => {
    setLoading(true)
    try {
      setStatus(await withMinDelay(getStatus()))
      return true
    } catch {
      return false
    } finally {
      setLoading(false)
    }
  }, [])
  useEffect(() => { load() }, [load])
  const handleRefresh = async () => {
    const ok = await load()
    setRefreshMsg(ok ? '已刷新' : '刷新失败')
    setTimeout(() => setRefreshMsg(''), 1500)
  }

  const formatDisk = (bytes: number) => {
    if (bytes >= 1e12) return `${(bytes / 1e12).toFixed(1)} TB`
    if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`
    if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(1)} MB`
    return `${(bytes / 1e3).toFixed(1)} KB`
  }

  return (
    <div className="page-container" style={{ padding: 'var(--space-12) var(--space-10)', maxWidth: '1200px', margin: '0 auto' }}>
      <PageHeader title="系统状态" description="系统配置与运行状态"
        actions={
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            {refreshMsg && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--status-success)', fontWeight: 500 }}>{refreshMsg}</span>}
            {/* Notion ghost button: 4px radius, 8px 12px padding */}
            <button onClick={handleRefresh} disabled={loading}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '6px',
                padding: '6px 12px', borderRadius: '4px',
                fontSize: 'var(--text-sm)', border: '1px solid var(--border-default)',
                background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer', fontWeight: 500,
                opacity: loading ? 0.5 : 1,
              }}>
              <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> 刷新
            </button>
          </div>
        }
      />
      {status ? (
        <div className="status-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-6)' }}>
          <div>
            <SectionHeader title="系统信息" />
            {/* Notion card: 12px radius, whisper border */}
            <div style={{ borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', border: '1px solid var(--border-default)', background: 'var(--bg-card)', boxShadow: 'var(--shadow-sm)' }}>
              <Row label="版本" value={status.version} />
              <Row label="Python" value={status.system?.python_version?.split(' ')[0] || '—'} />
              <Row label="平台" value={status.system?.platform || '—'} />
              <Row label="工作区" value={status.config.workspace} monospace />
              <Row label="磁盘" value={status.system ? `${formatDisk(status.system.disk_usage_bytes)} / ${formatDisk(status.system.disk_total_bytes)}` : '—'} />
              <Row label="LLM 模型" value={status.config.model} />
              <Row label="查询模型" value={status.config.query_model} />
              <Row label="API 端点" value={status.config.api_base} monospace />
              <Row label="API Key" value={status.config.has_api_key ? '已配置' : '未配置'} />
              <Row label="提供商" value={status.config.llm_provider} />
            </div>
          </div>
          <div>
            <SectionHeader title="文件统计" />
            {/* Notion card: 12px radius, whisper border, shadow */}
            <div style={{ borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', border: '1px solid var(--border-default)', background: 'var(--bg-card)', boxShadow: 'var(--shadow-sm)' }}>
              <Row label="总计" value={String(status.manifests.total)} />
              <Row label="已摄入" value={String(status.manifests.ingested)} />
              <Row label="已编译" value={String(status.manifests.compiled)} />
              <Row label="Wiki" value={String(status.manifests.promoted_to_wiki)} />
              <Row label="Curated" value={String(status.manifests.promoted)} />
              <Row label="失败" value={String(status.manifests.failed)} />
              <Row label="概念数" value={String(status.manifests.concepts_count ?? 0)} />
              <Row label="摘要数" value={String(status.manifests.summaries_count ?? 0)} />
              {Object.keys(status.manifests.by_type).length > 0 && (
                <div style={{ marginTop: 'var(--space-6)', paddingTop: 'var(--space-6)', borderTop: '1px solid var(--border-default)' }}>
                  <SectionHeader title="文件类型分布" />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                    {Object.entries(status.manifests.by_type).map(([type, count]: [string, number]) => (
                      <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
                        <span style={{
                          width: '56px', fontSize: 'var(--text-xs)', textAlign: 'right',
                          color: 'var(--text-dimmed)', fontWeight: 500, textTransform: 'uppercase',
                        }}>{type}</span>
                        {/* Notion bar: 4px radius */}
                        <div style={{ flex: 1, height: '20px', borderRadius: '4px', overflow: 'hidden', background: 'var(--bg-elevated)' }}>
                          <div style={{
                            height: '100%', borderRadius: '4px',
                            width: `${Math.max((count / status.manifests.total) * 100, 3)}%`,
                            background: 'var(--color-primary-bg)',
                            borderLeft: `2px solid var(--color-primary)`,
                          }} />
                        </div>
                        <span style={{
                          width: '28px', fontSize: 'var(--text-xs)', textAlign: 'right',
                          fontWeight: 500, color: 'var(--text-muted)',
                          fontVariantNumeric: 'tabular-nums',
                        }}>{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div style={{
          borderRadius: 'var(--radius-lg)', padding: 'var(--space-16)',
          textAlign: 'center', fontSize: 'var(--text-sm)',
          border: '1px solid var(--border-default)', color: 'var(--text-muted)',
        }}>
          {loading ? '加载中...' : '无法连接后端 API'}
        </div>
      )}
    </div>
  )
}
