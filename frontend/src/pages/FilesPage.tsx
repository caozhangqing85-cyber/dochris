import { useEffect, useState, useCallback, useRef } from 'react'
import { Search, Upload, FileText, RefreshCw, X, ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react'
import { formatBytes, statusLabel, withMinDelay } from '@/lib/utils'
import { getManifests, uploadFiles, resetFailedFiles } from '@/lib/api'
import { classifyRequestError, type RequestErrorInfo } from '@/lib/errors'
import type { ManifestItem } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import EmptyState from '@/components/ui/EmptyState'
import RequestErrorState from '@/components/ui/RequestErrorState'

const STATUS_COLORS: Record<string, { color: string; bg: string }> = {
  ingested: { color: 'var(--status-info)', bg: 'var(--status-info-bg)' },
  compiling: { color: 'var(--status-warning)', bg: 'var(--status-warning-bg)' },
  compiled: { color: 'var(--status-success)', bg: 'var(--status-success-bg)' },
  failed: { color: 'var(--status-error)', bg: 'var(--status-error-bg)' },
  promoted_to_wiki: { color: 'var(--color-primary)', bg: 'var(--color-primary-bg)' },
  promoted: { color: 'var(--color-primary)', bg: 'var(--color-primary-bg)' },
}

const PAGE_SIZE = 20

const btnPrimary: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: '6px',
  padding: '8px 16px', borderRadius: '4px',
  fontSize: 'var(--text-sm)', fontWeight: 600,
  color: 'var(--bg-card)', background: 'var(--color-primary)',
  border: 'none', cursor: 'pointer',
  transition: 'background 120ms ease-in-out',
}

const btnGhost: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: '6px',
  padding: '8px', borderRadius: '4px',
  background: 'transparent', border: 'none',
  color: 'var(--text-muted)', cursor: 'pointer',
}

export default function FilesPage() {
  const [files, setFiles] = useState<ManifestItem[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('')
  const [selected, setSelected] = useState<ManifestItem | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState<{ tone: 'success' | 'warning' | 'error'; text: string } | null>(null)
  const [page, setPage] = useState(1)
  const [dragOver, setDragOver] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [resetMsg, setResetMsg] = useState('')
  const [loadError, setLoadError] = useState<RequestErrorInfo | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const detailsDialogRef = useRef<HTMLDivElement>(null)
  const detailsCloseRef = useRef<HTMLButtonElement>(null)
  const selectedTriggerRef = useRef<HTMLElement | null>(null)

  const loadFiles = useCallback(async (isCancelled: () => boolean = () => false) => {
    try {
      const nextFiles = await withMinDelay(getManifests())
      if (isCancelled()) return
      setFiles(nextFiles)
      setLoadError(null)
    } catch (e) {
      if (!isCancelled()) setLoadError(classifyRequestError(e))
    }
    finally {
      if (!isCancelled()) setLoading(false)
    }
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    await loadFiles()
  }, [loadFiles])

  useEffect(() => {
    let cancelled = false
    queueMicrotask(() => {
      void loadFiles(() => cancelled)
    })
    return () => { cancelled = true }
  }, [loadFiles])

  const filtered = files.filter((f) => {
    if (filter && f.status !== filter) return false
    if (search && !f.title.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const failedCount = files.filter((file) => file.status === 'failed').length

  const closeDetails = useCallback(() => {
    setSelected(null)
    queueMicrotask(() => selectedTriggerRef.current?.focus())
  }, [])

  const openDetails = (file: ManifestItem, trigger: HTMLElement) => {
    selectedTriggerRef.current = trigger
    setSelected(file)
  }

  useEffect(() => {
    if (!selected) return

    const previousOverflow = document.body.style.overflow
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeDetails()
        return
      }
      if (event.key !== 'Tab') return

      const dialog = detailsDialogRef.current
      if (!dialog) return

      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      )).filter((element) => !element.hasAttribute('hidden'))

      if (focusable.length === 0) {
        event.preventDefault()
        dialog.focus()
        return
      }

      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', handleKeyDown)
    queueMicrotask(() => detailsCloseRef.current?.focus())

    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [closeDetails, selected])

  const doUpload = async (fileList: FileList | File[]) => {
    if (!fileList.length) return
    setUploading(true); setUploadMsg(null)
    try {
      const res = await uploadFiles(Array.from(fileList))
      await load()
      // 部分成功契约：分别展示 成功/跳过/失败 与逐文件错误
      if (res.failed > 0) {
        const reasons = res.errors?.length ? `，原因：${res.errors.join('；')}` : ''
        const skippedNote = res.skipped > 0 ? `，跳过重复 ${res.skipped} 个` : ''
        setUploadMsg({ tone: 'warning', text: `上传完成：成功 ${res.ingested} 个，失败 ${res.failed} 个${skippedNote}${reasons}` })
      } else if (res.skipped > 0) {
        setUploadMsg({ tone: 'success', text: `上传完成：成功 ${res.ingested} 个，跳过重复 ${res.skipped} 个` })
      } else {
        setUploadMsg({ tone: 'success', text: `成功上传 ${res.ingested} 个文件` })
      }
    } catch (err) { setUploadMsg({ tone: 'error', text: '上传失败: ' + (err as Error).message }) }
    finally { setUploading(false) }
  }

  const handleResetFailed = async () => {
    if (failedCount === 0) {
      setResetMsg('当前没有失败文件需要重置')
      return
    }
    if (!window.confirm(`将 ${failedCount} 个失败文件重置为待编译状态？此操作不会删除源文件。`)) return

    setResetting(true); setResetMsg('')
    try {
      const res = await resetFailedFiles()
      setResetMsg(`已重置 ${res.reset_count} 个失败文件`)
      await load()
    } catch (err) { setResetMsg('重置失败: ' + (err as Error).message) }
    finally { setResetting(false) }
  }

  const handleUpload = () => {
    const input = fileInputRef.current || document.createElement('input')
    input.type = 'file'; input.multiple = true
    input.accept = '.pdf,.md,.txt,.doc,.docx,.html,.htm,.rst,.epub,.mobi,.azw3,.fb2,.mp3,.m4a,.wav,.flac,.aac,.ogg,.opus,.mp4,.mkv,.avi,.mov,.wmv,.flv,.webm,.jpg,.jpeg,.png,.gif,.bmp,.svg,.webp'
    input.onchange = async (e) => {
      const fileList = (e.target as HTMLInputElement).files
      if (fileList?.length) doUpload(fileList)
    }
    input.click()
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false)
    if (e.dataTransfer.files?.length) doUpload(e.dataTransfer.files)
  }

  const handleSearchChange = (value: string) => {
    setSearch(value)
    setPage(1)
  }

  const handleFilterChange = (value: string) => {
    setFilter(value)
    setPage(1)
  }

  const pageHeader = (
    <PageHeader title="文件管理" description="管理知识库中的源文件"
      actions={
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <button onClick={handleUpload} disabled={uploading}
            style={{ ...btnPrimary, opacity: uploading ? 0.5 : 1 }}>
            <Upload size={15} /> {uploading ? '上传中...' : '上传文件'}
          </button>
          <button onClick={handleResetFailed} disabled={resetting || failedCount === 0}
            style={{ ...btnGhost, opacity: resetting || failedCount === 0 ? 0.45 : 1, padding: '6px 10px', fontSize: 'var(--text-sm)', fontWeight: 500, border: '1px solid var(--border-default)', borderRadius: '4px' }}
            title={failedCount === 0 ? '当前没有失败文件' : `将 ${failedCount} 个失败文件重置为待编译状态`}>
            <RotateCcw size={13} className={resetting ? 'animate-spin' : ''} /> 重置失败 ({failedCount})
          </button>
          <button onClick={load} disabled={loading} aria-label="刷新文件列表"
            style={{ ...btnGhost, opacity: loading ? 0.5 : 1 }}>
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      }
    />
  )

  if (loadError) return (
    <div className="page-container" style={{ padding: 'var(--space-12) var(--space-10)', maxWidth: '100%', margin: '0 auto' }}>
      {pageHeader}
      <RequestErrorState error={loadError} onRetry={load} retrying={loading} />
    </div>
  )

  return (
    <div className="page-container" style={{ padding: 'var(--space-12) var(--space-10)', maxWidth: '100%', margin: '0 auto' }}>
      {pageHeader}

      {/* Hidden file input for accessibility */}
      <input ref={fileInputRef} type="file" multiple
        accept=".pdf,.md,.txt,.doc,.docx,.html,.htm,.rst,.epub,.mobi,.azw3,.fb2,.mp3,.m4a,.wav,.flac,.aac,.ogg,.opus,.mp4,.mkv,.avi,.mov,.wmv,.flv,.webm,.jpg,.jpeg,.png,.gif,.bmp,.svg,.webp"
        style={{ display: 'none' }} />

      {uploadMsg && (
        <div style={{
          padding: 'var(--space-3) var(--space-4)', marginBottom: 'var(--space-4)',
          fontSize: 'var(--text-sm)', borderRadius: '4px', fontWeight: 500,
          background: uploadMsg.tone === 'error' ? 'var(--status-error-bg)'
            : uploadMsg.tone === 'warning' ? 'var(--status-warning-bg)'
            : 'var(--status-success-bg)',
          color: uploadMsg.tone === 'error' ? 'var(--status-error)'
            : uploadMsg.tone === 'warning' ? 'var(--status-warning)'
            : 'var(--status-success)',
          border: `1px solid ${uploadMsg.tone === 'error' ? 'var(--status-error-border)' : uploadMsg.tone === 'warning' ? 'var(--status-warning-border)' : 'var(--status-success-border)'}`,
        }}>
          {uploadMsg.text}
        </div>
      )}

      {resetMsg && (
        <div style={{
          padding: 'var(--space-3) var(--space-4)', marginBottom: 'var(--space-4)',
          fontSize: 'var(--text-sm)', borderRadius: '4px', fontWeight: 500,
          background: resetMsg.startsWith('重置失败') ? 'var(--status-error-bg)' : 'var(--status-info-bg)',
          color: resetMsg.startsWith('重置失败') ? 'var(--status-error)' : 'var(--status-info)',
        }}>
          {resetMsg}
        </div>
      )}

      {/* Search & Filter */}
      <div className="search-filter-bar" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-5)' }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <Search size={15} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dimmed)' }} />
          <input style={{
            width: '100%', padding: '6px 10px 6px 32px', borderRadius: '4px',
            fontSize: 'var(--text-sm)', border: '1px solid var(--border-default)',
            background: 'var(--bg-input)', color: 'var(--text-primary)', outline: 'none',
            lineHeight: 1.5,
          }} placeholder="搜索文件名..." value={search} onChange={(e) => handleSearchChange(e.target.value)} />
        </div>
        <select style={{
          padding: '6px 10px', borderRadius: '4px', fontSize: 'var(--text-sm)',
          border: '1px solid var(--border-default)', background: 'var(--bg-input)',
          color: 'var(--text-primary)', outline: 'none', cursor: 'pointer',
        }} value={filter} onChange={(e) => handleFilterChange(e.target.value)}>
          <option value="">全部状态</option>
          <option value="ingested">已摄入</option>
          <option value="compiled">已编译</option>
          <option value="failed">失败</option>
          <option value="promoted">已晋升</option>
        </select>
      </div>

      {/* Table or drag-and-drop zone */}
      {filtered.length > 0 ? (
        <div className="table-scroll" style={{ borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-default)', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--bg-elevated)' }}>
                {['文件名', '类型', '状态', '大小', '质量分'].map((h) => (
                  <th key={h} style={{
                    textAlign: 'left', padding: '8px 16px',
                    fontSize: 'var(--text-xs)', fontWeight: 600,
                    color: 'var(--text-dimmed)',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paged.map((f) => {
                const sc = STATUS_COLORS[f.status] || { color: 'var(--text-muted)', bg: 'var(--bg-elevated)' }
                return (
                  <tr key={f.id} onClick={(event) => openDetails(f, event.currentTarget)}
                    tabIndex={0}
                    aria-haspopup="dialog"
                    aria-label={`查看 ${f.title} 详情`}
                    onKeyDown={(event) => {
                      if (event.key !== 'Enter' && event.key !== ' ') return
                      event.preventDefault()
                      openDetails(f, event.currentTarget)
                    }}
                    style={{ borderTop: '1px solid var(--border-subtle)', cursor: 'pointer' }}
                    onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
                    <td style={{ padding: '8px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <FileText size={15} style={{ color: 'var(--text-dimmed)', flexShrink: 0 }} />
                        <span style={{ fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.title}</span>
                      </div>
                    </td>
                    <td style={{ padding: '8px 16px', fontSize: 'var(--text-sm)', color: 'var(--text-muted)', fontWeight: 400 }}>{f.type}</td>
                    <td style={{ padding: '8px 16px' }}>
                      <span style={{
                        display: 'inline-flex', padding: '2px 8px',
                        borderRadius: 'var(--radius-full)',
                        fontSize: 'var(--text-xs)', fontWeight: 600, letterSpacing: '0.125px',
                        background: sc.bg, color: sc.color,
                      }}>
                        {statusLabel(f.status)}
                      </span>
                    </td>
                    <td style={{ padding: '8px 16px', fontSize: 'var(--text-sm)', color: 'var(--text-muted)', fontWeight: 400 }}>{formatBytes(f.size_bytes)}</td>
                    <td style={{
                      padding: '8px 16px', fontSize: 'var(--text-sm)', fontWeight: 600,
                      color: (f.quality_score ?? 0) >= 85 ? 'var(--status-success)' : (f.quality_score ?? 0) >= 60 ? 'var(--status-warning)' : 'var(--status-error)',
                    }}>
                      {f.quality_score ?? '-'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div
          style={{
            borderRadius: 'var(--radius-lg)', border: dragOver ? '2px dashed var(--color-primary)' : '1px solid var(--border-default)',
            background: dragOver ? 'var(--color-primary-bg)' : 'transparent',
            transition: 'border-color 200ms ease, background 200ms ease',
          }}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          <EmptyState icon={<FileText size={28} />} title={loading ? '加载中...' : '暂无文件'}
            description={loading ? '' : '拖拽文件到此处或点击「上传文件」添加知识源文件'} />
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: 'var(--space-3) 0', marginTop: 'var(--space-4)',
        }}>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)' }}>
            共 {filtered.length} 个文件，第 {page}/{totalPages} 页
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)' }}>
            <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1}
              style={{ ...btnGhost, opacity: page <= 1 ? 0.3 : 1, padding: '4px 8px' }}>
              <ChevronLeft size={14} />
            </button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const p = Math.max(1, Math.min(page - 2, totalPages - 4)) + i
              if (p > totalPages) return null
              return (
                <button key={p} onClick={() => setPage(p)}
                  style={{
                    padding: '4px 10px', borderRadius: '4px', border: 'none',
                    fontSize: 'var(--text-xs)', fontWeight: p === page ? 600 : 400,
                    cursor: 'pointer',
                    background: p === page ? 'var(--color-primary-bg)' : 'transparent',
                    color: p === page ? 'var(--color-primary)' : 'var(--text-muted)',
                  }}>
                  {p}
                </button>
              )
            })}
            <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page >= totalPages}
              style={{ ...btnGhost, opacity: page >= totalPages ? 0.3 : 1, padding: '4px 8px' }}>
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {selected && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 50,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'var(--bg-overlay)',
        }} onClick={closeDetails}>
          <div ref={detailsDialogRef} className="modal-content" style={{
            width: '100%', maxWidth: '480px',
            borderRadius: 'var(--radius-lg)', padding: 'var(--space-6)',
            background: 'var(--bg-card)', boxShadow: 'var(--shadow-lg)',
          }} onClick={(e) => e.stopPropagation()}
            role="dialog" aria-modal="true"
            aria-labelledby="file-details-title" aria-describedby="file-details-description">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-5)' }}>
              <h3 id="file-details-title" style={{
                fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)',
                margin: 0, letterSpacing: '-0.25px',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>{selected.title}</h3>
              <button ref={detailsCloseRef} onClick={closeDetails} aria-label="关闭文件详情"
                style={{ padding: '4px', borderRadius: '4px', border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-dimmed)' }}>
                <X size={16} />
              </button>
            </div>
            <p id="file-details-description" style={{ margin: 'calc(var(--space-3) * -1) 0 var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)' }}>
              文件只读详情。按 Escape 关闭并返回文件列表。
            </p>
            <div>
              {[
                ['ID', selected.id], ['类型', selected.type], ['状态', statusLabel(selected.status)],
                ['大小', formatBytes(selected.size_bytes)], ['质量分', String(selected.quality_score ?? '-')],
                ['路径', selected.file_path],
              ].map(([label, value]) => (
                <div key={label} style={{
                  display: 'flex', justifyContent: 'space-between', padding: '8px 0',
                  borderTop: '1px solid var(--border-subtle)',
                }}>
                  <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', fontWeight: 400 }}>{label}</span>
                  <span style={{
                    fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--text-primary)',
                    maxWidth: '60%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textAlign: 'right',
                  }}>{value}</span>
                </div>
              ))}
              {selected.compiled_summary && (
                <div style={{ paddingTop: 'var(--space-3)' }}>
                  <div style={{ fontSize: 'var(--text-xs)', marginBottom: 'var(--space-1)', color: 'var(--text-dimmed)', fontWeight: 600 }}>摘要</div>
                  <p style={{ fontSize: 'var(--text-sm)', lineHeight: 'var(--leading-relaxed)', color: 'var(--text-secondary)', margin: 0, fontWeight: 400 }}>{selected.compiled_summary.one_line}</p>
                </div>
              )}
              {selected.error_message && (
                <div style={{ marginTop: 'var(--space-3)', padding: 'var(--space-3)', fontSize: 'var(--text-sm)', borderRadius: '4px', background: 'var(--status-error-bg)', color: 'var(--status-error)', fontWeight: 400 }}>
                  {selected.error_message}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
