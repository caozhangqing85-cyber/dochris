interface EmptyStateProps {
  icon: React.ReactNode
  title: string
  description: string
  action?: React.ReactNode
}

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: 'var(--space-16) var(--space-8)',
      textAlign: 'center',
    }}>
      <div style={{ marginBottom: 'var(--space-4)', color: 'var(--text-dimmed)', opacity: 0.6 }}>
        {icon}
      </div>
      <div style={{
        fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--text-secondary)',
        marginBottom: 'var(--space-1)',
      }}>
        {title}
      </div>
      <div style={{
        fontSize: 'var(--text-sm)', color: 'var(--text-muted)',
        maxWidth: '340px', lineHeight: 'var(--leading-relaxed)', fontWeight: 400,
      }}>
        {description}
      </div>
      {action && <div style={{ marginTop: 'var(--space-5)' }}>{action}</div>}
    </div>
  )
}
