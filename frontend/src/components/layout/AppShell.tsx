import type { ReactNode } from 'react'
import { Sidebar } from './Sidebar'

interface AppShellProps {
  children: ReactNode
}

/**
 * App frame: a permanent left sidebar on desktop plus a scrollable main
 * content column. Layout only — it owns no routing or data logic.
 */
export function AppShell({ children }: AppShellProps) {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">
        <div className="app-content">{children}</div>
      </main>
    </div>
  )
}
