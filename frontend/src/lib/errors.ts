export type RequestErrorKind =
  | 'offline'
  | 'unauthorized'
  | 'forbidden'
  | 'timeout'
  | 'cancelled'
  | 'gateway'
  | 'server'
  | 'unknown'

export interface RequestErrorInfo {
  kind: RequestErrorKind
  title: string
  message: string
  diagnostic: string
  retryable: boolean
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  if (typeof error === 'string') return error
  if (error && typeof error === 'object' && 'message' in error) {
    return String((error as { message?: unknown }).message ?? '')
  }
  return String(error ?? '')
}

function getErrorStatus(error: unknown, message: string): number | null {
  if (error && typeof error === 'object') {
    const status = (error as { status?: unknown; statusCode?: unknown }).status
    const statusCode = (error as { status?: unknown; statusCode?: unknown }).statusCode
    if (typeof status === 'number') return status
    if (typeof statusCode === 'number') return statusCode
  }
  const match = message.match(/\b(401|403|408|429|5\d{2})\b/)
  return match ? Number(match[1]) : null
}

function getErrorCode(error: unknown): string {
  if (!error || typeof error !== 'object' || !('code' in error)) return ''
  return String((error as { code?: unknown }).code ?? '').toUpperCase()
}

export function classifyRequestError(error: unknown): RequestErrorInfo {
  const message = getErrorMessage(error)
  const normalized = message.toLowerCase()
  const status = getErrorStatus(error, message)
  const code = getErrorCode(error)

  if (code === 'OFFLINE' || (
    normalized.includes('failed to fetch')
    || normalized.includes('networkerror')
    || normalized.includes('network error')
    || normalized.includes('load failed')
  )) {
    return {
      kind: 'offline',
      title: '无法连接后端服务',
      message: message || '浏览器没有收到后端响应。',
      diagnostic: '请确认 dochris 后端服务已启动，前端代理配置正确，并检查本机网络或跨域拦截。',
      retryable: true,
    }
  }

  if (code === 'UNAUTHORIZED' || status === 401) {
    return {
      kind: 'unauthorized',
      title: '认证失败',
      message: message || '当前 API Key 无效或未提供。',
      diagnostic: '请在设置页检查 API Key，或确认后端没有启用错误的认证配置。',
      retryable: false,
    }
  }

  if (code === 'FORBIDDEN' || status === 403) {
    return {
      kind: 'forbidden',
      title: '没有访问权限',
      message: message || '后端拒绝了当前请求。',
      diagnostic: '请确认 API Key 权限、后端访问策略和当前工作区配置。',
      retryable: false,
    }
  }

  if (code === 'ABORTED' || error instanceof DOMException && error.name === 'AbortError') {
    return {
      kind: 'cancelled',
      title: '请求已取消',
      message: message || '这次请求已被取消。',
      diagnostic: '如果是你主动触发的取消，可以忽略；如果不是，请重试并检查浏览器控制台。',
      retryable: false,
    }
  }

  if (
    code === 'TIMEOUT'
    ||
    status === 408
    || error instanceof DOMException && error.name === 'TimeoutError'
    || normalized.includes('timeout')
    || normalized.includes('timed out')
  ) {
    return {
      kind: 'timeout',
      title: '请求超时',
      message: message || '后端处理时间超过前端等待上限。',
      diagnostic: '可以重试；如果持续出现，请检查索引规模、LLM 响应时间和后端日志。',
      retryable: true,
    }
  }

  if (status === 502) {
    return {
      kind: 'gateway',
      title: '后端网关不可用',
      message: message || '前端代理无法连接 dochris 后端。',
      diagnostic: '请确认 dochris 后端已启动，并检查前端代理目标是否指向 127.0.0.1:8000。',
      retryable: true,
    }
  }

  if (status !== null && status >= 500) {
    return {
      kind: 'server',
      title: '后端服务异常',
      message: message || `后端返回 ${status}。`,
      diagnostic: '请查看后端终端日志、最近一次请求 trace，以及当前知识库数据是否损坏。',
      retryable: true,
    }
  }

  return {
    kind: 'unknown',
    title: '请求失败',
    message: message || '前端无法识别这次请求失败的原因。',
    diagnostic: '请重试；如果仍失败，请保留浏览器控制台和后端日志用于诊断。',
    retryable: true,
  }
}
