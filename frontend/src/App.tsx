import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import { AnalyzePage } from './pages/AnalyzePage'
import { DashboardPage } from './pages/DashboardPage'
import { ReportDetailPage } from './pages/ReportDetailPage'
import { SavedReportsPage } from './pages/SavedReportsPage'
import { WatchlistsPage } from './pages/WatchlistsPage'

export default function App() {
  return (
    <BrowserRouter>
      <header className="app-header">
        <span className="app-name">Investment Bot</span>
        <nav>
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/analyze">Analyze</NavLink>
          <NavLink to="/watchlists">Watchlists</NavLink>
          <NavLink to="/reports">Saved Reports</NavLink>
        </nav>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/analyze" element={<AnalyzePage />} />
          <Route path="/watchlists" element={<WatchlistsPage />} />
          <Route path="/reports" element={<SavedReportsPage />} />
          <Route path="/reports/:id" element={<ReportDetailPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
