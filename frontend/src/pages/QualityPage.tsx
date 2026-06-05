import { useEffect, useState, useCallback, useMemo } from 'react'
import { Target, TrendingUp, Award, AlertTriangle, RefreshCw, RotateCcw, ShieldCheck, Shield, ShieldQuestion, ShieldAlert, ChevronDown, ChevronUp } from 'lucide-react'
import { getStatus, resetLowQuality, getManifests } from '@/lib/api'
import { withMinDelay } from '@/lib/utils'
import type { StatusResponse, ManifestItem } from '@/types'
import StatCard from '@/components/ui/StatCard'
import PageHeader from '@/components/ui/PageHeader'
import SectionHeader from '@/components/ui/SectionHeader'

const PROV_CONFIG: Record<string, { color: string; bg: string; icon: React.ReactNode; label: string }> = {
  extracted: { color: 'var(--status-success)', bg: 'var(--status-success-bg)', icon: <ShieldCheck size={15} />, label: '直接提取' },
  merged: { color: 'var(--color-primary)', bg: 'var(--color-primary-bg)', icon: <Shield size={15} />, label: '合并重组' },
  inferred: { color: 'var(--status-warning)', bg: 'var(--status-warning-bg)', icon: <ShieldQuestion size={15} />, label: '推断补充' },
  ambiguous: { color: 'var(--status-error)', bg: 'var(--status-error-bg)', icon: <ShieldAlert size={15} />, label: '来源不明' },
}

export default function QualityPage() {
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [manifests, setManifests] = useState<ManifestItem[]>([])
  const [loading, setLoading] = useState(true)
  const [resetting, setResetting] = useState(false)
  const [resetMsg, setResetMsg] = useState('')
  const [showScoringHelp, setShowScoringHelp] = useState(false)
  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [s, m] = await Promise.all([withMinDelay(getStatus()), getManifests()])
      setStatus(s)
      setManifests(m)
    } catch { /* */ }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { load() }, [load])

  const handleReset = async () => {
    setResetting(true); setResetMsg('')
    try { const res = await resetLowQuality(); setResetMsg(`已重置 ${res.reset_count} 个文件`); await load() }
    catch (e) { setResetMsg('重置失败: ' + (e as Error).message) }
    finally { setResetting(false) }
  }

  const threshold = status?.config?.min_quality_score ?? 85
  const m = status?.manifests
  const total = m?.total ?? 0; const compiled = m?.compiled ?? 0; const failed = m?.failed ?? 0
  const ingested = m?.ingested ?? 0
  const rate = total ? compiled / total : 0

  const compiledPct = total ? Math.round((compiled / total) * 100) : 0
  const failedPct = total ? Math.round((failed / total) * 100) : 0
  const ingestedPct = total ? Math.round((ingested / total) * 100) : 0

  const buckets = [
    { label: '失败', pct: failedPct, color: 'var(--status-error)', bg: 'var(--status-error-bg)' },
    { label: '待编译', pct: ingestedPct, color: 'var(--status-info)', bg: 'var(--status-info-bg)' },
    { label: '已编译', pct: compiledPct, color: 'var(--status-success)', bg: 'var(--status-success-bg)' },
  ]

  // 溯源分布统计
  const provenanceStats = useMemo(() => {
    const counts: Record<string, number> = { extracted: 0, merged: 0, inferred: 0, ambiguous: 0 }
    let noProvenance = 0
    for (const f of manifests) {
      const prov = f.compiled_summary?.provenance?.overall_label
      if (prov && prov in counts) counts[prov]++
      else if (f.status === 'compiled' || f.status === 'promoted_to_wiki' || f.status === 'promoted') noProvenance++
    }
    return { counts, noProvenance }
  }, [manifests])

  // Lint 统计
  const lintStats = useMemo(() => {
    let passed = 0; let failed = 0; let noLint = 0; let totalWarnings = 0; let totalErrors = 0
    for (const f of manifests) {
      const lint = f.compiled_summary?.lint
      if (!lint) { if (f.status === 'compiled' || f.status === 'promoted_to_wiki' || f.status === 'promoted') noLint++; continue }
      if (lint.passed) passed++
      else { failed++; totalErrors += lint.error_count }
      totalWarnings += lint.warning_count
    }
    return { passed, failed, noLint, totalWarnings, totalErrors }
  }, [manifests])

  return (
    <div className="page-container" style={{ padding: 'var(--space-12) var(--space-10)', maxWidth: '100%', margin: '0 auto' }}>
      <PageHeader title="质量监控" description="知识库编译质量分析"
        actions={<button onClick={load} disabled={loading} style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '6px 12px', borderRadius: '4px', fontSize: 'var(--text-sm)', border: '1px solid var(--border-default)', background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer', fontWeight: 500, opacity: loading ? 0.5 : 1 }}><RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> 刷新</button>}
      />

      <SectionHeader title="质量概览" />
      <div className="grid-responsive" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-4)', marginBottom: 'var(--space-10)' }}>
        <StatCard label="总文件" value={total} color="var(--color-primary)" icon={<Target size={18} />} />
        <StatCard label="已编译" value={compiled} color="var(--status-success)" icon={<TrendingUp size={18} />} />
        <StatCard label="失败" value={failed} color="var(--status-error)" icon={<AlertTriangle size={18} />} />
        <StatCard label="质量阈值" value={threshold} color="var(--status-info)" icon={<Award size={18} />} />
      </div>

      <SectionHeader title="质量分布" />
      <div style={{ borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', border: '1px solid var(--border-default)', marginBottom: 'var(--space-6)', background: 'var(--bg-card)', boxShadow: 'var(--shadow-sm)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          {buckets.map((b) => (
            <div key={b.label} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
              <span style={{ width: '48px', fontSize: 'var(--text-xs)', textAlign: 'right', color: 'var(--text-dimmed)', fontWeight: 400 }}>{b.label}</span>
              <div style={{ flex: 1, height: '22px', borderRadius: '4px', overflow: 'hidden', background: 'var(--bg-elevated)' }}>
                <div style={{ height: '100%', borderRadius: '4px', width: `${Math.max(b.pct, 2)}%`, background: b.bg, borderLeft: `2px solid ${b.color}`, transition: 'width 0.4s ease' }} />
              </div>
              <span style={{ width: '36px', fontSize: 'var(--text-xs)', textAlign: 'right', fontWeight: 500, color: 'var(--text-muted)' }}>{b.pct}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── 质量评分说明 ── */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <button onClick={() => setShowScoringHelp(!showScoringHelp)}
          style={{
            display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer',
            background: 'none', border: 'none', padding: '4px 0',
            color: 'var(--text-muted)', fontSize: 'var(--text-sm)', fontWeight: 500,
          }}>
          {showScoringHelp ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          质量评分说明
        </button>
        {showScoringHelp && (
          <div style={{
            borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
            border: '1px solid var(--border-default)', marginTop: 'var(--space-2)',
            background: 'var(--bg-card)', fontSize: 'var(--text-sm)',
            color: 'var(--text-secondary)', lineHeight: 'var(--leading-relaxed)',
          }}>
            <p style={{ margin: '0 0 var(--space-3)', fontWeight: 600, color: 'var(--text-primary)' }}>评分维度（总分 100）</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-2)' }}>
              {[
                ['结构完整性', '摘要是否包含 one_line、key_points、detailed_summary'],
                ['信息密度', '关键术语、方法论、核心概念的数量'],
                ['学习价值', '是否包含可操作的学习建议和知识增量'],
                ['语言质量', '语法正确性、表达清晰度、无模板化痕迹'],
                ['概念质量', '概念命名是否准确、解释是否充分'],
                ['整体一致性', '各部分之间是否逻辑自洽、无矛盾'],
                ['信息覆盖', '是否完整覆盖原文的关键要点'],
              ].map(([dim, desc]) => (
                <div key={dim} style={{ padding: 'var(--space-2) 0', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{dim}</span>
                  <span style={{ display: 'block', fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', marginTop: '2px' }}>{desc}</span>
                </div>
              ))}
            </div>
            <p style={{ margin: 'var(--space-3) 0 0', fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)' }}>
              质量阈值默认 85 分。低于阈值的文件可通过「重置低质量」重新编译。
            </p>
          </div>
        )}
      </div>

      {/* ── 溯源标签分布 (Layer 0) ── */}
      <SectionHeader title="溯源标签分布" />
      <div style={{ borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', border: '1px solid var(--border-default)', marginBottom: 'var(--space-6)', background: 'var(--bg-card)', boxShadow: 'var(--shadow-sm)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-3)' }}>
          {Object.entries(PROV_CONFIG).map(([key, cfg]) => {
            const count = provenanceStats.counts[key] || 0
            return (
              <div key={key} style={{ padding: 'var(--space-3)', borderRadius: 'var(--radius-lg)', background: cfg.bg, display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <span style={{ color: cfg.color, display: 'flex' }}>{cfg.icon}</span>
                <div>
                  <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: cfg.color, lineHeight: 1.2 }}>{count}</div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', fontWeight: 500 }}>{cfg.label}</div>
                </div>
              </div>
            )
          })}
        </div>
        {provenanceStats.noProvenance > 0 && (
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', marginTop: 'var(--space-3)', fontWeight: 400 }}>
            {provenanceStats.noProvenance} 个已编译文件无溯源标签（需重新编译以生成标签）
          </p>
        )}
      </div>

      {/* ── Lint 校验统计 (Layer 1) ── */}
      <SectionHeader title="Lint 校验统计" />
      <div style={{ borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', border: '1px solid var(--border-default)', marginBottom: 'var(--space-6)', background: 'var(--bg-card)', boxShadow: 'var(--shadow-sm)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-3)' }}>
          <div style={{ padding: 'var(--space-3)', borderRadius: 'var(--radius-lg)', background: 'var(--status-success-bg)' }}>
            <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--status-success)', lineHeight: 1.2 }}>{lintStats.passed}</div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', fontWeight: 500 }}>Lint 通过</div>
          </div>
          <div style={{ padding: 'var(--space-3)', borderRadius: 'var(--radius-lg)', background: 'var(--status-error-bg)' }}>
            <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--status-error)', lineHeight: 1.2 }}>{lintStats.failed}</div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', fontWeight: 500 }}>Lint 未通过 ({lintStats.totalErrors} 错误)</div>
          </div>
          <div style={{ padding: 'var(--space-3)', borderRadius: 'var(--radius-lg)', background: 'var(--status-warning-bg)' }}>
            <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--status-warning)', lineHeight: 1.2 }}>{lintStats.totalWarnings}</div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', fontWeight: 500 }}>警告总计</div>
          </div>
        </div>
        {lintStats.noLint > 0 && (
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)', marginTop: 'var(--space-3)', fontWeight: 400 }}>
            {lintStats.noLint} 个已编译文件无 Lint 数据（需重新编译）
          </p>
        )}
      </div>

      <div style={{ borderRadius: 'var(--radius-lg)', padding: 'var(--space-4) var(--space-5)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', border: '1px solid var(--border-default)', background: 'var(--bg-card)' }}>
        <div>
          <div style={{ fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--text-primary)' }}>{rate >= 0.8 ? '整体质量优秀' : rate >= 0.6 ? '整体质量良好' : '需要改进'}</div>
          <div style={{ fontSize: 'var(--text-sm)', marginTop: '2px', color: 'var(--text-muted)', fontWeight: 400 }}>编译成功率: {total ? (rate * 100).toFixed(1) : 0}%</div>
        </div>
        <button onClick={handleReset} disabled={resetting}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '8px 16px', borderRadius: '4px', fontSize: '14px', fontWeight: 500, border: 'none', cursor: 'pointer', background: 'var(--bg-hover)', color: 'var(--text-secondary)', opacity: resetting ? 0.5 : 1 }}>
          {resetting ? <RefreshCw size={13} className="animate-spin" /> : <RotateCcw size={13} />} {resetting ? '重置中...' : '重置低质量'}
        </button>
      </div>
      {resetMsg && <p style={{ fontSize: 'var(--text-sm)', marginTop: 'var(--space-3)', color: resetMsg.startsWith('重置失败') ? 'var(--status-error)' : 'var(--color-primary)', fontWeight: 400 }}>{resetMsg}</p>}
    </div>
  )
}
