interface SectionHeaderProps {
  title: string
  action?: React.ReactNode
}

export default function SectionHeader({ title, action }: SectionHeaderProps) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: 'var(--space-4)',
    }}>
      <h2 style={{
        fontSize: 'var(--text-xs)', fontWeight: 600,
        textTransform: 'uppercase', letterSpacing: '0.125px',  /* Notion badge tracking */
        color: 'var(--text-dimmed)', margin: 0,
      }}>
        {title}
      </h2>
      {action}
    </div>
  )
}
