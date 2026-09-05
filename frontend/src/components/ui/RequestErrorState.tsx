import { AlertTriangle, RefreshCw } from 'lucide-react'
import type { RequestErrorInfo } from '@/lib/errors'

interface RequestErrorStateProps {
  error: RequestErrorInfo
  onRetry?: () => void
  retrying?: boolean
}

export default function RequestErrorState({ error, onRetry, retrying = false }: RequestErrorStateProps) {
  return (
    <div style={{
      border: '1px solid var(--status-error)',
      borderRadius: 'var(--radius-lg)',
      background: 'var(--status-error-bg)',
      padding: 'var(--space-6)',
      marginBottom: 'var(--space-6)',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)' }}>
        <AlertTriangle size={20} style={{ color: 'var(--status-error)', flexShrink: 0, marginTop: '2px' }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--status-error)', marginBottom: 'var(--space-1)' }}>
            {error.title}
          </div>
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)', lineHeight: 'var(--leading-relaxed)', marginBottom: 'var(--space-2)' }}>
            {error.message}
          </div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', lineHeight: 'var(--leading-relaxed)' }}>
            {error.diagnostic}
          </div>
        </div>
        {onRetry && error.retryable && (
          <button
            onClick={() => onRetry()}
            disabled={retrying}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: '4px',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              border: '1px solid var(--status-error)',
              background: 'var(--bg-card)',
              color: 'var(--status-error)',
              cursor: retrying ? 'default' : 'pointer',
              opacity: retrying ? 0.6 : 1,
              flexShrink: 0,
            }}
          >
            <RefreshCw size={13} className={retrying ? 'animate-spin' : ''} />
            重试
          </button>
        )}
      </div>
    </div>
  )
}
