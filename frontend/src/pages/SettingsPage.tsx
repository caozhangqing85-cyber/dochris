import { useEffect, useState, useCallback } from 'react'
import { Save, RefreshCw, Plug, Loader2, CheckCircle2, XCircle } from 'lucide-react'
import { getConfig, updateConfig, getStatus } from '@/lib/api'
import { withMinDelay } from '@/lib/utils'
import PageHeader from '@/components/ui/PageHeader'
import SectionHeader from '@/components/ui/SectionHeader'

export default function SettingsPage() {
  const [form, setForm] = useState({
    api_base: '', api_key: '', model: '', query_model: '',
    llm_provider: 'openai_compat', temperature: 0.1, workspace: '',
    vector_store: 'chromadb',
  })
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const loadConfig = useCallback(async () => {
    setLoading(true)
    try {
      const c = await withMinDelay(getConfig())
      setForm({
        api_base: c.api_base || '', api_key: c.api_key ? `${c.api_key.slice(0, 6)}...${c.api_key.slice(-4)}` : '',
        model: c.model || '', query_model: c.query_model || '',
        llm_provider: c.llm_provider || 'openai_compat', temperature: c.temperature ?? 0.1,
        workspace: c.workspace || '',
        vector_store: c.vector_store || 'chromadb',
      })
    } catch { /* */ }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { loadConfig() }, [loadConfig])

  const handleSave = async () => {
    setSaving(true); setMessage(null)
    if (!form.api_base.trim()) {
      setMessage({ type: 'error', text: 'API 端点不能为空' }); setSaving(false); return
    }
    if (!form.model.trim()) {
      setMessage({ type: 'error', text: '主模型不能为空' }); setSaving(false); return
    }
    try {
      const u: Record<string, string | number> = {}
      if (form.api_base) u.api_base = form.api_base
      if (form.api_key && !form.api_key.includes('...')) u.api_key = form.api_key
      if (form.model) u.model = form.model
      if (form.query_model) u.query_model = form.query_model
      u.llm_provider = form.llm_provider; u.temperature = form.temperature
      if (form.vector_store) u.vector_store = form.vector_store
      if (form.workspace) u.workspace = form.workspace
      await updateConfig(u); setMessage({ type: 'success', text: '配置已保存' })
    } catch (e) { setMessage({ type: 'error', text: '保存失败: ' + (e as Error).message }) }
    finally { setSaving(false) }
  }

  const handleTest = async () => {
    setTesting(true); setMessage(null)
    try { await getStatus(); setMessage({ type: 'success', text: '连接成功！' }) }
    catch (e) { setMessage({ type: 'error', text: '连接失败: ' + (e as Error).message }) }
    finally { setTesting(false) }
  }

  /* Notion input style */
  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '6px 10px', borderRadius: '4px',
    fontSize: 'var(--text-sm)', border: '1px solid var(--border-default)',
    background: 'var(--bg-input)', color: 'var(--text-primary)', outline: 'none',
    lineHeight: 1.5,
  }
  const labelStyle: React.CSSProperties = {
    display: 'block', fontSize: 'var(--text-sm)', fontWeight: 500,
    color: 'var(--text-muted)', marginBottom: 'var(--space-2)',
  }

  return (
    <div className="page-container" style={{ padding: 'var(--space-12) var(--space-10)', maxWidth: '1200px', margin: '0 auto' }}>
      <PageHeader title="系统设置" description="配置 LLM 模型、API 端点和工作区" />

      <SectionHeader title="API 配置" />
      {/* Notion card: 12px radius, shadow */}
      <div style={{
        borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
        border: '1px solid var(--border-default)', marginBottom: 'var(--space-10)',
        background: 'var(--bg-card)', boxShadow: 'var(--shadow-sm)',
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
          <div>
            <label style={labelStyle}>API 端点</label>
            <input style={{ ...inputStyle, fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)' }}
              placeholder="https://open.bigmodel.cn/api/paas/v4"
              value={form.api_base} onChange={(e) => setForm({ ...form, api_base: e.target.value })} />
          </div>
          <div>
            <label style={labelStyle}>API 密钥</label>
            <input style={inputStyle} type="password" placeholder="输入 API Key..."
              value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} />
          </div>
          <div className="settings-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-6)' }}>
            <div>
              <label style={labelStyle}>主模型</label>
              <input style={inputStyle} placeholder="glm-5.1"
                value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} />
            </div>
            <div>
              <label style={labelStyle}>查询模型</label>
              <input style={inputStyle} placeholder="glm-4-flash"
                value={form.query_model} onChange={(e) => setForm({ ...form, query_model: e.target.value })} />
            </div>
          </div>
        </div>
      </div>

      <SectionHeader title="高级配置" />
      {/* Notion card: 12px radius, shadow */}
      <div style={{
        borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
        border: '1px solid var(--border-default)', marginBottom: 'var(--space-10)',
        background: 'var(--bg-card)', boxShadow: 'var(--shadow-sm)',
      }}>
        <div className="settings-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-6)', marginBottom: 'var(--space-6)' }}>
          <div>
            <label style={labelStyle}>LLM 提供商</label>
            <select style={inputStyle} value={form.llm_provider} onChange={(e) => setForm({ ...form, llm_provider: e.target.value })}>
              <option value="openai_compat">OpenAI Compatible</option>
              <option value="ollama">Ollama</option>
            </select>
          </div>
          <div>
            <label style={labelStyle}>向量数据库</label>
            <select style={inputStyle} value={form.vector_store} onChange={(e) => setForm({ ...form, vector_store: e.target.value })}>
              <option value="chromadb">ChromaDB (默认)</option>
              <option value="faiss">FAISS (轻量级)</option>
              <option value="leann">LEANN (超低存储)</option>
            </select>
          </div>
        </div>
        <div className="settings-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-6)', marginBottom: 'var(--space-6)' }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--space-3)' }}>
              <label style={{ fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--text-muted)' }}>温度参数</label>
              <span style={{
                fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-primary)',
                fontVariantNumeric: 'tabular-nums',
              }}>{form.temperature}</span>
            </div>
            <input type="range" min={0} max={1} step={0.05} value={form.temperature}
              onChange={(e) => setForm({ ...form, temperature: +e.target.value })}
              style={{ width: '100%', accentColor: 'var(--color-primary)', marginTop: 'var(--space-1)' }} />
          </div>
        </div>
        <div>
          <label style={labelStyle}>工作区路径</label>
          <input style={{ ...inputStyle, fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)' }}
            placeholder="~/.dochris/knowledge-base"
            value={form.workspace} onChange={(e) => setForm({ ...form, workspace: e.target.value })} />
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-8)' }}>
        {/* Notion primary button: 4px radius, 8px 16px padding */}
        <button onClick={handleSave} disabled={saving}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: '6px',
            padding: '8px 16px', borderRadius: '4px',
            fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--bg-card)',
            background: 'var(--color-primary)', border: 'none', cursor: 'pointer',
            opacity: saving ? 0.5 : 1,
          }}>
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} 保存
        </button>
        {/* Notion secondary button: 4px radius, border */}
        <button onClick={handleTest} disabled={testing}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: '6px',
            padding: '8px 16px', borderRadius: '4px',
            fontSize: 'var(--text-sm)', fontWeight: 500, border: '1px solid var(--border-default)',
            background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer',
            opacity: testing ? 0.5 : 1,
          }}>
          {testing ? <Loader2 size={14} className="animate-spin" /> : <Plug size={14} />} {testing ? '测试中...' : '测试连接'}
        </button>
        <button onClick={loadConfig} disabled={loading}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: '6px',
            padding: '8px 16px', borderRadius: '4px',
            fontSize: 'var(--text-sm)', fontWeight: 500, border: '1px solid var(--border-default)',
            background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer',
            opacity: loading ? 0.5 : 1,
          }}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> {loading ? '加载中...' : '重置'}
        </button>
      </div>

      {/* Notion message: 4px radius */}
      {message && (
        <div style={{
          borderRadius: '4px', padding: 'var(--space-4)',
          display: 'flex', alignItems: 'center', gap: 'var(--space-3)',
          fontSize: 'var(--text-sm)',
          background: message.type === 'success' ? 'var(--status-success-bg)' : 'var(--status-error-bg)',
          border: `1px solid ${message.type === 'success' ? 'var(--status-success-border)' : 'var(--status-error-border)'}`,
        }}>
          {message.type === 'success'
            ? <CheckCircle2 size={16} style={{ color: 'var(--status-success)' }} />
            : <XCircle size={16} style={{ color: 'var(--status-error)' }} />}
          <span style={{ color: message.type === 'success' ? 'var(--status-success)' : 'var(--status-error)' }}>
            {message.text}
          </span>
        </div>
      )}
    </div>
  )
}
