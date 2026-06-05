import { statusLabel } from '@/lib/utils'

const VARIANT_STYLES: Record<string, React.CSSProperties> = {
  ingested: { background: 'var(--status-info-bg)', color: 'var(--status-info)', border: '1px solid var(--status-info-border)' },
  compiling: { background: 'var(--status-warning-bg)', color: 'var(--status-warning)', border: '1px solid var(--status-warning-border)' },
  compiled: { background: 'var(--status-success-bg)', color: 'var(--status-success)', border: '1px solid var(--status-success-border)' },
  failed: { background: 'var(--status-error-bg)', color: 'var(--status-error)', border: '1px solid var(--status-error-border)' },
  compile_failed: { background: 'var(--status-error-bg)', color: 'var(--status-error)', border: '1px solid var(--status-error-border)' },
  promoted: { background: 'var(--color-primary-bg)', color: 'var(--color-primary)', border: '1px solid var(--color-primary-border)' },
  promoted_to_wiki: { background: 'var(--color-primary-bg)', color: 'var(--color-primary)', border: '1px solid var(--color-primary-border)' },
}

export default function Badge({ status }: { status: string }) {
  const variant = VARIANT_STYLES[status] || { background: 'var(--bg-elevated)', color: 'var(--text-muted)', border: '1px solid var(--border-default)' }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '4px 8px', borderRadius: 'var(--radius-full)',  /* Notion pill badge 9999px */
      fontSize: 'var(--text-xs)', fontWeight: 600, letterSpacing: '0.125px',  /* Notion badge tracking */
      ...variant,
    }}>
      {statusLabel(status)}
    </span>
  )
}
