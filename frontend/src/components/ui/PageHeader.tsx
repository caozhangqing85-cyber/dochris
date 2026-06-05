interface PageHeaderProps {
  title: string
  description?: string
  actions?: React.ReactNode
}

export default function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start',
      justifyContent: 'space-between',
      marginBottom: 'var(--space-10)',
      gap: 'var(--space-6)',
    }}>
      <div style={{ minWidth: 0 }}>
        <h1 style={{
          fontSize: 'var(--text-2xl)', fontWeight: 700,
          color: 'var(--text-primary)', letterSpacing: '-0.625px',  /* Notion sub-heading tracking */
          margin: 0, lineHeight: 1.23,
        }}>
          {title}
        </h1>
        {description && (
          <p style={{
            fontSize: 'var(--text-base)', color: 'var(--text-muted)',
            marginTop: 'var(--space-1)', lineHeight: 'var(--leading-normal)', fontWeight: 400,
          }}>
            {description}
          </p>
        )}
      </div>
      {actions && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', flexShrink: 0 }}>
          {actions}
        </div>
      )}
    </div>
  )
}
