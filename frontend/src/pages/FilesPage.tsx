import { useEffect, useState, useCallback, useRef } from 'react'
import { Search, Upload, FileText, RefreshCw, X, ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react'
import { formatBytes, statusLabel, withMinDelay } from '@/lib/utils'
import { getManifests, uploadFiles, resetFailedFiles } from '@/lib/api'
import type { ManifestItem } from '@/types'
import PageHeader from '@/components/ui/PageHeader'
import EmptyState from '@/components/ui/EmptyState'

const STATUS_COLORS: Record<string, { color: string; bg: string }> = {
  ingested: { color: 'var(--status-info)', bg: 'var(--status-info-bg)' },
  compiling: { color: 'var(--status-warning)', bg: 'var(--status-warning-bg)' },
  compiled: { color: 'var(--status-success)', bg: 'var(--status-success-bg)' },
  failed: { color: 'var(--status-error)', bg: 'var(--status-error-bg)' },
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
  const [uploadMsg, setUploadMsg] = useState('')
  const [page, setPage] = useState(1)
  const [dragOver, setDragOver] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [resetMsg, setResetMsg] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try { setFiles(await withMinDelay(getManifests())) } catch { /* */ }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { load() }, [load])

  const filtered = files.filter((f) => {
    if (filter && f.status !== filter) return false
    if (search && !f.title.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  // Reset page on filter/search change
  useEffect(() => { setPage(1) }, [search, filter])

  const doUpload = async (fileList: FileList | File[]) => {
    if (!fileList.length) return
    setUploading(true); setUploadMsg('')
    try {
      const res = await uploadFiles(Array.from(fileList))
      setUploadMsg(`成功上传 ${res.ingested} 个文件`); await load()
    } catch (err) { setUploadMsg('上传失败: ' + (err as Error).message) }
    finally { setUploading(false) }
  }

  const handleResetFailed = async () => {
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

  return (
    <div className="page-container" style={{ padding: 'var(--space-12) var(--space-10)', maxWidth: '100%', margin: '0 auto' }}>
      <PageHeader title="文件管理" description="管理知识库中的源文件"
        actions={
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <button onClick={handleUpload} disabled={uploading}
              style={{ ...btnPrimary, opacity: uploading ? 0.5 : 1 }}>
              <Upload size={15} /> {uploading ? '上传中...' : '上传文件'}
            </button>
            <button onClick={handleResetFailed} disabled={resetting}
              style={{ ...btnGhost, opacity: resetting ? 0.5 : 1, padding: '6px 10px', fontSize: 'var(--text-sm)', fontWeight: 500, border: '1px solid var(--border-default)', borderRadius: '4px' }}
              title="将所有失败文件重置为待编译状态">
              <RotateCcw size={13} className={resetting ? 'animate-spin' : ''} /> 重置失败
            </button>
            <button onClick={load} disabled={loading} style={{ ...btnGhost, opacity: loading ? 0.5 : 1 }}>
              <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
        }
      />

      {/* Hidden file input for accessibility */}
      <input ref={fileInputRef} type="file" multiple
        accept=".pdf,.md,.txt,.doc,.docx,.html,.htm,.rst,.epub,.mobi,.azw3,.fb2,.mp3,.m4a,.wav,.flac,.aac,.ogg,.opus,.mp4,.mkv,.avi,.mov,.wmv,.flv,.webm,.jpg,.jpeg,.png,.gif,.bmp,.svg,.webp"
        style={{ display: 'none' }} />

      {uploadMsg && (
        <div style={{
          padding: 'var(--space-3) var(--space-4)', marginBottom: 'var(--space-4)',
          fontSize: 'var(--text-sm)', borderRadius: '4px', fontWeight: 500,
          background: uploadMsg.startsWith('上传失败') ? 'var(--status-error-bg)' : 'var(--status-success-bg)',
          color: uploadMsg.startsWith('上传失败') ? 'var(--status-error)' : 'var(--status-success)',
        }}>
          {uploadMsg}
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
          }} placeholder="搜索文件名..." value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select style={{
          padding: '6px 10px', borderRadius: '4px', fontSize: 'var(--text-sm)',
          border: '1px solid var(--border-default)', background: 'var(--bg-input)',
          color: 'var(--text-primary)', outline: 'none', cursor: 'pointer',
        }} value={filter} onChange={(e) => setFilter(e.target.value)}>
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
                  <tr key={f.id} onClick={() => setSelected(f)}
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
        }} onClick={() => setSelected(null)}>
          <div className="modal-content" style={{
            width: '100%', maxWidth: '480px',
            borderRadius: 'var(--radius-lg)', padding: 'var(--space-6)',
            background: 'var(--bg-card)', boxShadow: 'var(--shadow-lg)',
          }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-5)' }}>
              <h3 style={{
                fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)',
                margin: 0, letterSpacing: '-0.25px',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>{selected.title}</h3>
              <button onClick={() => setSelected(null)}
                style={{ padding: '4px', borderRadius: '4px', border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-dimmed)' }}>
                <X size={16} />
              </button>
            </div>
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
