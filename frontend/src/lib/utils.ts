import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Ensure an async operation takes at least `ms` milliseconds, so loading spinners are visible.
 * 默认 150ms（防闪烁），生产环境后端快时不拖慢体验。 */
export async function withMinDelay<T>(promise: Promise<T>, ms = 150): Promise<T> {
  const [result] = await Promise.all([promise, new Promise((r) => setTimeout(r, ms))])
  return result
}

export function formatBytes(bytes: number): string {
  // 负数/0/非有限值统一兜底，避免 Math.log 产生 NaN
  if (!bytes || !Number.isFinite(bytes) || bytes < 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    compiled: 'text-emerald-400',
    ingested: 'text-sky-400',
    failed: 'text-red-400',
    compile_failed: 'text-red-400',
    promoted_to_wiki: 'text-violet-400',
    promoted: 'text-amber-400',
  }
  return map[status] || 'text-zinc-400'
}

export function statusBg(status: string): string {
  const map: Record<string, string> = {
    compiled: 'bg-emerald-400/10 text-emerald-400 border-emerald-400/20',
    ingested: 'bg-sky-400/10 text-sky-400 border-sky-400/20',
    failed: 'bg-red-400/10 text-red-400 border-red-400/20',
    compile_failed: 'bg-red-400/10 text-red-400 border-red-400/20',
    promoted_to_wiki: 'bg-violet-400/10 text-violet-400 border-violet-400/20',
    promoted: 'bg-amber-400/10 text-amber-400 border-amber-400/20',
  }
  return map[status] || 'bg-zinc-400/10 text-zinc-400 border-zinc-400/20'
}

export function statusLabel(status: string): string {
  const map: Record<string, string> = {
    compiled: '已编译',
    compiling: '编译中',
    ingested: '待编译',
    failed: '失败',
    compile_failed: '编译失败',
    promoted_to_wiki: 'Wiki',
    promoted: 'Curated',
  }
  return map[status] || status
}

export function qualityColor(score: number): string {
  if (score >= 80) return 'text-emerald-400'
  if (score >= 60) return 'text-amber-400'
  return 'text-red-400'
}
