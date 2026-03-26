import { NavLink, Route, Routes } from 'react-router-dom'
import { AlertsPage } from './pages/AlertsPage'
import { AnalyticsStatusPage } from './pages/AnalyticsStatusPage'
import { DashboardPage } from './pages/DashboardPage'
import { HomePage } from './pages/HomePage'
import { LiveMapPage } from './pages/LiveMapPage'
import { LiveMonitoringPage } from './pages/LiveMonitoringPage'
import './App.css'

const navItems = [
  { to: '/', label: 'Overview' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/monitoring', label: 'Live Monitoring' },
  { to: '/alerts', label: 'Alerts' },
  { to: '/analytics', label: 'Analytics + Status' },
  { to: '/live-map', label: 'Live Map' },
]

function App() {
  return (
    <div className="app-shell">
      <header className="top-nav glass">
        <div className="brand">
          <strong>AEGIS-RS</strong>
          <span>Intelligent Road Safety Monitoring</span>
        </div>
        <nav className="nav-links">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === '/'}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="content-area">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/monitoring" element={<LiveMonitoringPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/analytics" element={<AnalyticsStatusPage />} />
          <Route path="/live-map" element={<LiveMapPage />} />
        </Routes>
      </main>

      <footer className="footer glass">
        <p>AEGIS-RS • AI-Based Multi-Hazard Monitoring • Fog Prediction Focus</p>
      </footer>
    </div>
  )
}

export default App
