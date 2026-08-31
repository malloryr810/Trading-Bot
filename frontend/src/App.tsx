import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { AnalyzePage } from './pages/AnalyzePage'
import { DashboardPage } from './pages/DashboardPage'
import { DiscoverPage } from './pages/DiscoverPage'
import { PaperTradingPage } from './pages/PaperTradingPage'
import { ReportDetailPage } from './pages/ReportDetailPage'
import { SavedReportsPage } from './pages/SavedReportsPage'
import { WatchlistSnapshotDetailPage } from './pages/WatchlistSnapshotDetailPage'
import { WatchlistsPage } from './pages/WatchlistsPage'

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/discover" element={<DiscoverPage />} />
          <Route path="/analyze" element={<AnalyzePage />} />
          <Route path="/watchlists" element={<WatchlistsPage />} />
          <Route
            path="/watchlists/:watchlistId/snapshots/:snapshotId"
            element={<WatchlistSnapshotDetailPage />}
          />
          <Route path="/paper-trading" element={<PaperTradingPage />} />
          <Route path="/reports" element={<SavedReportsPage />} />
          <Route path="/reports/:id" element={<ReportDetailPage />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  )
}
