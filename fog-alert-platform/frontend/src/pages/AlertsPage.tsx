import BorderGlow from '@/components/BorderGlow'
import ShinyText from '@/components/ShinyText'

const alerts = [
  { severity: 'HIGH', location: 'NH75', visibility: '30m', speed: '25 km/h' },
  { severity: 'MEDIUM', location: 'Ring Road', visibility: '60m', speed: '40 km/h' },
  { severity: 'LOW', location: 'City Bypass', visibility: '120m', speed: '55 km/h' },
]

export function AlertsPage() {
  return (
    <div className="page">
      <section>
        <BorderGlow className="panel glass">
          <div className="alert-toolbar">
            <ShinyText text="Real-time Alert Feed" className="text-xl font-bold" color="#ffffff" shineColor="#ffffff" />
            <select className="filter-select" defaultValue="all">
              <option value="all">Filter: All Severity</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          <div className="alert-list">
            {alerts.map((alert) => (
              <BorderGlow key={`${alert.severity}-${alert.location}`} className={`alert-item ${alert.severity.toLowerCase()}`}>
                <strong>🔴 {alert.severity} RISK</strong>
                <p>Location: {alert.location}</p>
                <p>Visibility: {alert.visibility}</p>
                <p>Recommended Speed: {alert.speed}</p>
              </BorderGlow>
            ))}
          </div>
        </BorderGlow>
      </section>
    </div>
  )
}
