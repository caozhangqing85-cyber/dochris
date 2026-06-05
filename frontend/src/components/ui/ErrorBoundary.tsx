import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback
      return (
        <div style={{ padding: '48px 40px', maxWidth: '600px', margin: '0 auto', textAlign: 'center' }}>
          <div style={{
            padding: '24px', borderRadius: '12px',
            border: '1px solid rgba(212, 86, 86, 0.15)',
            background: 'rgba(212, 86, 86, 0.06)',
          }}>
            <div style={{ fontSize: '16px', fontWeight: 700, color: 'rgba(0,0,0,0.95)', marginBottom: '8px' }}>
              页面渲染出错
            </div>
            <pre style={{
              fontSize: '13px', color: '#d45656', textAlign: 'left',
              background: 'rgba(0,0,0,0.03)', padding: '12px', borderRadius: '8px',
              overflow: 'auto', maxHeight: '200px', margin: '0 0 16px',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>
              {this.state.error?.message}
            </pre>
            <button onClick={() => this.setState({ hasError: false, error: null })}
              style={{
                padding: '8px 20px', borderRadius: '4px', fontSize: '14px', fontWeight: 600,
                color: '#fff', background: '#0075de', border: 'none', cursor: 'pointer',
              }}>
              重试
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
