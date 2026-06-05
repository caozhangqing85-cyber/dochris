import { BrowserRouter, Routes, Route } from 'react-router-dom'
import ErrorBoundary from '@/components/ui/ErrorBoundary'
import AppLayout from '@/components/layout/AppLayout'
import DashboardPage from '@/pages/DashboardPage'
import FilesPage from '@/pages/FilesPage'
import CompilePage from '@/pages/CompilePage'
import QueryPage from '@/pages/QueryPage'
import QualityPage from '@/pages/QualityPage'
import GraphPage from '@/pages/GraphPage'
import StatusPage from '@/pages/StatusPage'
import SettingsPage from '@/pages/SettingsPage'

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
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
          </Route>
        </Routes>
      </ErrorBoundary>
    </BrowserRouter>
  )
}
