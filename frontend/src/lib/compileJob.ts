const ACTIVE_COMPILE_STATUSES = new Set([
  'accepted',
  'queued',
  'running',
  'cancelling',
])

export function isCompileJobActive(status: string): boolean {
  return ACTIVE_COMPILE_STATUSES.has(status)
}

export function compileJobPercent(
  job: Pick<{ total: number; processed: number }, 'total' | 'processed'>,
): number {
  if (job.total <= 0) return 0
  return Math.round(Math.min(1, Math.max(0, job.processed / job.total)) * 100)
}
