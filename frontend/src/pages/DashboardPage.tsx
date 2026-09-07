import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { FolderOpen, FileCheck, AlertTriangle, Clock, Brain, Database, RefreshCw } from 'lucide-react'
import { getStatus } from '@/lib/api'
import { classifyRequestError, type RequestErrorInfo } from '@/lib/errors'
import { withMinDelay } from '@/lib/utils'
import type { StatusResponse } from '@/types'
import StatCard from '@/components/ui/StatCard'
import PageHeader from '@/components/ui/PageHeader'
import RequestErrorState from '@/components/ui/RequestErrorState'
import SectionHeader from '@/components/ui/SectionHeader'

export default function DashboardPage() {
  const [data, setData] = useState<StatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<RequestErrorInfo | null>(null)
  const [refreshMsg, setRefreshMsg] = useState('')
  const navigate = useNavigate()

  const load = useCallback(async () => {
    setLoading(true); setLoadError(null)
    try { setData(await withMinDelay(getStatus())); return true }
    catch (e) { setLoadError(classifyRequestError(e)); return false }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    let cancelled = false
    const loadInitial = async () => {
      try {
        const nextData = await withMinDelay(getStatus())
        if (cancelled) return
        setData(nextData)
        setLoadError(null)
      } catch (e) {
        if (!cancelled) setLoadError(classifyRequestError(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void loadInitial()
    return () => { cancelled = true }
  }, [])

  const handleRefresh = async () => {
    const ok = await load()
    setRefreshMsg(ok ? '已刷新' : '刷新失败')
    setTimeout(() => setRefreshMsg(''), 2000)
  }

  if (loadError) return (
    <div className="page-container" style={{ padding: 'var(--space-12) var(--space-10)', maxWidth: '100%', margin: '0 auto' }}>
      <PageHeader title="仪表盘" description="Dochris 知识库系统" />
      <RequestErrorState error={loadError} onRetry={load} retrying={loading} />
    </div>
  )

  const m = data?.manifests
  const c = data?.config

  const stats = [
    { label: '总文件', value: m?.total ?? '-', color: 'var(--color-primary)', icon: <FolderOpen size={18} /> },
    { label: '已编译', value: m?.compiled ?? '-', color: 'var(--status-success)', icon: <FileCheck size={18} /> },
    { label: '待编译', value: m?.ingested ?? '-', color: 'var(--status-info)', icon: <Clock size={18} /> },
    { label: '失败', value: m?.failed ?? '-', color: 'var(--status-error)', icon: <AlertTriangle size={18} /> },
  ]

  const actions = [
    { label: '上传文件', desc: '添加知识源文件', icon: FolderOpen, path: '/files' },
    { label: '开始编译', desc: '编译待处理文件', icon: FileCheck, path: '/compile' },
    { label: '查询知识', desc: 'AI 知识检索', icon: Brain, path: '/query' },
    { label: '知识图谱', desc: '可视化概念关系', icon: Database, path: '/graph' },
  ]

  return (
    <div className="page-container" style={{ padding: 'var(--space-12) var(--space-10)', maxWidth: '100%', margin: '0 auto' }}>
      <div className="page-header-responsive">
        <PageHeader title="仪表盘" description={data ? `Dochris 知识库系统 · v${data.version}` : 'Dochris 知识库系统'}
          actions={
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
              {refreshMsg && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--status-success)', fontWeight: 500 }}>{refreshMsg}</span>}
              <button onClick={handleRefresh} disabled={loading}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: '6px',
                  padding: '6px 12px', borderRadius: '4px',
                  fontSize: 'var(--text-sm)', border: '1px solid var(--border-default)',
                  background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer', fontWeight: 500,
                }}>
                <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> 刷新
              </button>
            </div>
          }
        />
      </div>

      <SectionHeader title="数据概览" />
      {m && m.total === 0 && (
        <div style={{
          padding: 'var(--space-6)', borderRadius: 'var(--radius-lg)',
          border: '1px dashed var(--border-default)', marginBottom: 'var(--space-6)',
          background: 'var(--bg-elevated)', textAlign: 'center',
        }}>
          <p style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 var(--space-2)' }}>
            知识库还是空的
          </p>
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', margin: 0 }}>
            前往「文件管理」上传你的第一份文档，开始构建知识库
          </p>
        </div>
      )}
      <div className="grid-responsive" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-4)', marginBottom: 'var(--space-12)' }}>
        {stats.map((s) => <StatCard key={s.label} {...s} />)}
      </div>

      <SectionHeader title="快捷操作" />
      <div className="grid-responsive" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-4)', marginBottom: 'var(--space-12)' }}>
        {actions.map((a) => (
          <button key={a.path} onClick={() => navigate(a.path)}
            style={{
              textAlign: 'left', borderRadius: 'var(--radius-lg)',
              padding: 'var(--space-5)',
              border: '1px solid var(--border-default)',
              background: 'var(--bg-card)', boxShadow: 'var(--shadow-sm)',
              cursor: 'pointer', transition: 'box-shadow 200ms cubic-bezier(0.2, 0, 0, 1)',
            }}
            onMouseEnter={(e) => e.currentTarget.style.boxShadow = 'var(--shadow-md)'}
            onMouseLeave={(e) => e.currentTarget.style.boxShadow = 'var(--shadow-sm)'}>
            <a.icon size={20} style={{ color: 'var(--text-dimmed)', marginBottom: 'var(--space-3)' }} />
            <div style={{ fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--text-primary)' }}>{a.label}</div>
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', marginTop: '2px', fontWeight: 400 }}>{a.desc}</div>
          </button>
        ))}
      </div>

      {c && (
        <>
          <SectionHeader title="系统配置" />
          <div style={{
            borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
            border: '1px solid var(--border-default)', background: 'var(--bg-card)',
            boxShadow: 'var(--shadow-sm)',
          }}>
            <div className="grid-responsive-3" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-4) var(--space-8)' }}>
              {[
                { label: 'LLM 模型', value: c.model || '-' },
                { label: '查询模型', value: c.query_model || '-' },
                { label: 'API Key', value: c.has_api_key ? '已配置' : '未配置', color: c.has_api_key ? 'var(--status-success)' : 'var(--status-error)' },
                { label: '提供商', value: c.llm_provider || '-' },
                { label: '质量阈值', value: String(c.min_quality_score) },
                { label: '工作区', value: c.workspace || '-' },
              ].map((item) => (
                <div key={item.label}>
                  <div style={{
                    fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)',
                    marginBottom: '2px', textTransform: 'uppercase',
                    letterSpacing: '0.125px', fontWeight: 600,
                  }}>
                    {item.label}
                  </div>
                  <div style={{
                    fontSize: 'var(--text-sm)', fontWeight: 500,
                    color: item.color || 'var(--text-primary)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {item.value}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
