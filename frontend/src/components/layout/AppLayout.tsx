import { useState, useEffect, useCallback, useRef } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, FolderOpen, PlayCircle, Search,
  Target, Activity, Share2, Settings, Menu, X, FileEdit,
} from 'lucide-react'
import { getStatus } from '@/lib/api'

const mainNav = [
  { to: '/', icon: LayoutDashboard, label: '仪表盘' },
  { to: '/files', icon: FolderOpen, label: '文件管理' },
  { to: '/compile', icon: PlayCircle, label: '编译控制' },
  { to: '/query', icon: Search, label: '知识查询' },
  { to: '/candidates', icon: FileEdit, label: '候选知识' },
]

const toolNav = [
  { to: '/quality', icon: Target, label: '质量监控' },
  { to: '/graph', icon: Share2, label: '知识图谱' },
  { to: '/status', icon: Activity, label: '系统状态' },
  { to: '/settings', icon: Settings, label: '系统设置' },
]

export default function AppLayout() {
  // 侧栏版本号：从 /status 动态获取，避免硬编码漂移
  const [appVersion, setAppVersion] = useState('')
  useEffect(() => {
    let alive = true
    getStatus().then((s) => { if (alive && s.version) setAppVersion(s.version) }).catch(() => undefined)
    return () => { alive = false }
  }, [])
  const [mobileMenuState, setMobileMenuState] = useState({ open: false, pathname: '' })
  const location = useLocation()
  const mobileOpen = mobileMenuState.open && mobileMenuState.pathname === location.pathname
  const mobileSidebarRef = useRef<HTMLElement>(null)
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null)
  const mobileCloseButtonRef = useRef<HTMLButtonElement>(null)
  const mainContentRef = useRef<HTMLElement>(null)
  const previousPathRef = useRef(location.pathname)
  const wasMobileOpenRef = useRef(false)

  const closeMobileMenu = useCallback(() => {
    setMobileMenuState({ open: false, pathname: location.pathname })
  }, [location.pathname])

  const openMobileMenu = useCallback(() => {
    setMobileMenuState({ open: true, pathname: location.pathname })
  }, [location.pathname])

  useEffect(() => {
    if (!mobileOpen) return

    const previousOverflow = document.body.style.overflow
    const focusCloseButton = requestAnimationFrame(() => mobileCloseButtonRef.current?.focus())
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeMobileMenu()
        return
      }
      if (event.key !== 'Tab') return

      const sidebar = mobileSidebarRef.current
      if (!sidebar) return
      const focusable = Array.from(sidebar.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ))
      if (focusable.length === 0) return

      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      } else if (!sidebar.contains(document.activeElement)) {
        event.preventDefault()
        first.focus()
      }
    }

    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      cancelAnimationFrame(focusCloseButton)
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [closeMobileMenu, mobileOpen])

  useEffect(() => {
    if (wasMobileOpenRef.current && !mobileOpen) {
      requestAnimationFrame(() => mobileMenuButtonRef.current?.focus())
    }
    wasMobileOpenRef.current = mobileOpen
  }, [mobileOpen])

  useEffect(() => {
    if (previousPathRef.current === location.pathname) return
    previousPathRef.current = location.pathname

    const focusHeading = requestAnimationFrame(() => {
      const heading = mainContentRef.current?.querySelector<HTMLElement>('h1')
      if (!heading) return
      heading.tabIndex = -1
      heading.focus({ preventScroll: true })
    })
    return () => cancelAnimationFrame(focusHeading)
  }, [location.pathname])

  const renderNavLink = (item: { to: string; icon: typeof LayoutDashboard; label: string }) => (
    <NavLink key={item.to} to={item.to} end={item.to === '/'}
      onClick={closeMobileMenu}
      style={({ isActive }) => ({
        display: 'flex', alignItems: 'center', gap: '10px',
        padding: '6px 8px', fontSize: '14px',
        lineHeight: 1.5, borderRadius: '4px',
        textDecoration: 'none',
        transition: 'background 120ms ease-in-out',
        background: isActive ? 'var(--color-primary-bg)' : 'transparent',
        color: isActive ? 'var(--color-primary)' : 'var(--text-secondary)',
        fontWeight: isActive ? 600 : 500,
      })}>
      <item.icon size={18} />
      <span>{item.label}</span>
    </NavLink>
  )

  const sidebarContent = (
    <>
      {/* Logo */}
      <div style={{ padding: '12px 8px 8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 8px' }}>
          <div style={{
            width: '22px', height: '22px', borderRadius: '4px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontSize: '13px', fontWeight: 700,
            background: 'var(--color-primary)',
          }}>D</div>
          <span style={{
            fontSize: '14px', fontWeight: 600,
            color: 'var(--text-primary)', lineHeight: 1.3,
          }}>Dochris</span>
        </div>
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, overflowY: 'auto', padding: '4px 8px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
          {mainNav.map(renderNavLink)}
        </div>
        <div style={{ margin: '8px 8px', borderTop: '1px solid var(--border-subtle)' }} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
          {toolNav.map(renderNavLink)}
        </div>
      </nav>

      {/* Footer */}
      <div style={{
        padding: '8px 16px',
        borderTop: '1px solid var(--border-subtle)',
        fontSize: '12px', color: 'var(--text-dimmed)', fontWeight: 400,
      }}>
        {appVersion ? `v${appVersion}` : ''}
      </div>
    </>
  )

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg-body)' }}>
      {/* Desktop sidebar */}
      <aside className="sidebar-desktop" style={{
        width: '240px', flexShrink: 0,
        display: 'flex', flexDirection: 'column',
        borderRight: '1px solid var(--border-default)',
        background: 'var(--bg-sidebar)',
      }}>
        {sidebarContent}
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 40,
          background: 'var(--bg-overlay)',
        }} onClick={closeMobileMenu} />
      )}

      {/* Mobile sidebar */}
      <aside ref={mobileSidebarRef} id="mobile-navigation-dialog" className="sidebar-mobile"
        role={mobileOpen ? 'dialog' : undefined} aria-modal={mobileOpen ? 'true' : undefined}
        aria-label={mobileOpen ? '主导航菜单' : undefined} aria-hidden={!mobileOpen} inert={!mobileOpen}
        style={{
        position: 'fixed', left: 0, top: 0, bottom: 0,
        width: '260px', zIndex: 50,
        display: 'flex', flexDirection: 'column',
        borderRight: '1px solid var(--border-default)',
        background: 'var(--bg-sidebar)',
        transform: mobileOpen ? 'translateX(0)' : 'translateX(-100%)',
        transition: 'transform 200ms cubic-bezier(0.2, 0, 0, 1)',
      }}>
        {/* Mobile close button */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '8px 8px 0' }}>
          <button ref={mobileCloseButtonRef} onClick={closeMobileMenu} aria-label="关闭导航菜单"
            style={{
              padding: '6px', borderRadius: '4px', border: 'none',
              background: 'transparent', cursor: 'pointer', color: 'var(--text-dimmed)',
            }}>
            <X size={18} />
          </button>
        </div>
        {sidebarContent}
      </aside>

      <main ref={mainContentRef} inert={mobileOpen} style={{ flex: 1, overflowY: 'auto' }}>
        {/* Mobile top bar */}
        <div className="mobile-header" style={{
          display: 'none',
          alignItems: 'center', gap: '10px',
          padding: '10px 16px',
          borderBottom: '1px solid var(--border-subtle)',
          background: 'var(--bg-sidebar)',
        }}>
          <button ref={mobileMenuButtonRef} onClick={openMobileMenu}
            aria-label="打开导航菜单" aria-controls="mobile-navigation-dialog" aria-expanded={mobileOpen}
            style={{
              padding: '6px', borderRadius: '4px', border: 'none',
              background: 'transparent', cursor: 'pointer', color: 'var(--text-primary)',
            }}>
            <Menu size={20} />
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{
              width: '22px', height: '22px', borderRadius: '4px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#fff', fontSize: '13px', fontWeight: 700,
              background: 'var(--color-primary)',
            }}>D</div>
            <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Dochris</span>
          </div>
        </div>
        <Outlet />
      </main>
    </div>
  )
}
