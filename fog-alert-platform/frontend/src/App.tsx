import { Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { AlertsPage } from './pages/AlertsPage'
import { AnalyticsStatusPage } from './pages/AnalyticsStatusPage'
import { DashboardPage } from './pages/DashboardPage'
import { HomePage } from './pages/HomePage'
import { LiveMapPage } from './pages/LiveMapPage'
import { LiveMonitoringPage } from './pages/LiveMonitoringPage'
import './App.css'
import { AnimatedOrbs } from './components/AnimatedOrbs'
import GooeyNav from './components/GooeyNav'

const navItems = [
  { to: '/', label: 'Overview' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/monitoring', label: 'Live Monitoring' },
  { to: '/alerts', label: 'Alerts' },
  { to: '/analytics', label: 'Analytics' },
  { to: '/live-map', label: 'Live Map' },
]

function App() {
  const navigate = useNavigate()
  const location = useLocation()
  const normalizedPath = location.pathname === '/video' ? '/monitoring' : location.pathname
  const activeNavIndex = Math.max(
    0,
    navItems.findIndex((item) => item.to === normalizedPath),
  )

  return (
    <div className="app-shell">
      <AnimatedOrbs />
      <header className="top-nav glass">
        <div className="brand">
          <strong>AEGIS-RS</strong>
          <span className="text-white">AI-Based Intelligent Multi-Hazard Road Monitoring System</span>
        </div>
        <div className="nav-links">
          <GooeyNav
            items={navItems.map((item) => ({ label: item.label, href: item.to }))}
            particleCount={15}
            particleDistances={[90, 10]}
            particleR={100}
            initialActiveIndex={0}
            activeIndex={activeNavIndex}
            animationTime={600}
            timeVariance={300}
            colors={[1, 2, 3, 1, 2, 3, 1, 4]}
            onItemSelect={(_index, item) => {
              if (location.pathname !== item.href) {
                navigate(item.href)
              }
            }}
          />
        </div>
      </header>

      <main className="content-area">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/monitoring" element={<LiveMonitoringPage />} />
          <Route path="/video" element={<LiveMonitoringPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/analytics" element={<AnalyticsStatusPage />} />
          <Route path="/live-map" element={<LiveMapPage />} />
        </Routes>
      </main>

      <footer className="footer glass text-white">
        <p>AEGIS-RS • AI-Based Multi-Hazard Monitoring • Fog Prediction Focus</p>
      </footer>
    </div>
  )
}

export default App
