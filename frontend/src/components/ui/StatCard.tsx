interface StatCardProps {
  label: string
  value: string | number
  color?: string
  icon?: React.ReactNode
}

export default function StatCard({ label, value, color = 'var(--color-primary)', icon }: StatCardProps) {
  return (
    <div style={{
      borderRadius: 'var(--radius-lg)',  /* Notion 12px card radius */
      padding: 'var(--space-5)',
      background: 'var(--bg-card)',
      border: '1px solid var(--border-default)',  /* Notion whisper border */
      boxShadow: 'var(--shadow-sm)',  /* Notion 4-layer card shadow */
    }}>
      {icon && (
        <div style={{
          width: '32px', height: '32px', borderRadius: 'var(--radius-md)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginBottom: 'var(--space-3)',
          background: `${color}0d`, color,
        }}>
          {icon}
        </div>
      )}
      <div style={{
        fontSize: 'var(--text-xl)', fontWeight: 700, lineHeight: 'var(--leading-tight)',
        color, letterSpacing: '-0.25px',  /* Notion Card Title tracking */
      }}>
        {value}
      </div>
      <div style={{
        fontSize: 'var(--text-sm)', marginTop: 'var(--space-1)',
        color: 'var(--text-dimmed)', fontWeight: 500,  /* Notion Caption weight */
      }}>
        {label}
      </div>
    </div>
  )
}
