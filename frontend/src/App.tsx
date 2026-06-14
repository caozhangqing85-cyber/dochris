import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import ErrorBoundary from '@/components/ui/ErrorBoundary'
import AppLayout from '@/components/layout/AppLayout'

// 路由懒加载：各页面按需加载为独立 chunk，减小首屏 bundle
// （GraphPage 含 D3 重依赖，拆分后首屏不加载）
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const FilesPage = lazy(() => import('@/pages/FilesPage'))
const CompilePage = lazy(() => import('@/pages/CompilePage'))
const QueryPage = lazy(() => import('@/pages/QueryPage'))
const QualityPage = lazy(() => import('@/pages/QualityPage'))
const GraphPage = lazy(() => import('@/pages/GraphPage'))
const StatusPage = lazy(() => import('@/pages/StatusPage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))

function PageLoader() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh', color: 'var(--text-muted)' }}>
      加载中…
    </div>
  )
}

function NotFound() {
  return (
    <div style={{ textAlign: 'center', padding: '80px 20px', color: 'var(--text-muted)' }}>
      <div style={{ fontSize: '48px', marginBottom: '16px' }}>404</div>
      <div style={{ marginBottom: '24px' }}>页面不存在</div>
      <Link to="/" style={{ color: 'var(--color-primary)' }}>返回首页</Link>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route element={<AppLayout />}>
              <Route index element={<DashboardPage />} />
              <Route path="files" element={<FilesPage />} />
              <Route path="compile" element={<CompilePage />} />
              <Route path="query" element={<QueryPage />} />
              <Route path="quality" element={<QualityPage />} />
              <Route path="graph" element={<GraphPage />} />
              <Route path="status" element={<StatusPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </Suspense>
      </ErrorBoundary>
    </BrowserRouter>
  )
}
