import { useEffect, useState, useMemo } from 'react'
import BorderGlow from '@/components/BorderGlow'
import ShinyText from '@/components/ShinyText'

type AlertItem = {
  id: string
  type?: string
  status?: 'open' | 'confirmed' | 'in_progress' | 'resolved' | string
  severity: 'HIGH' | 'MEDIUM' | 'LOW' | string
  location: string
  visibility?: string
  speed?: string
  detected_at?: string
  details?: string
}

const fallbackAlerts: AlertItem[] = [
  { id: 'fb-1', type: 'pothole', status: 'open', severity: 'HIGH', location: 'NH75 - Km 12', visibility: '20m', speed: '20 km/h', detected_at: new Date().toISOString(), details: 'Multiple deep potholes detected near median.' },
  { id: 'fb-2', type: 'fog', status: 'open', severity: 'HIGH', location: 'Ring Road - Sector 5', visibility: '15m', speed: '25 km/h', detected_at: new Date().toISOString(), details: 'Dense fog reducing visibility drastically.' },
  { id: 'fb-3', type: 'camera', status: 'in_progress', severity: 'MEDIUM', location: 'Bridge Cam A', visibility: '50m', speed: '40 km/h', detected_at: new Date().toISOString(), details: 'Camera feed intermittent, signal drops.' },
  { id: 'fb-4', type: 'pothole', status: 'in_progress', severity: 'MEDIUM', location: 'City Bypass - Exit 3', visibility: '80m', speed: '45 km/h', detected_at: new Date().toISOString(), details: 'Cluster of small potholes reported.' },
  { id: 'fb-5', type: 'fog', status: 'monitoring', severity: 'LOW', location: 'Coastal Hwy', visibility: '120m', speed: '60 km/h', detected_at: new Date().toISOString(), details: 'Light fog patch near sea-facing stretch.' },
  { id: 'fb-6', type: 'pothole', status: 'monitoring', severity: 'LOW', location: 'Market Street', visibility: '100m', speed: '30 km/h', detected_at: new Date().toISOString(), details: 'Single pothole on shoulder.' },
  { id: 'fb-7', type: 'camera', status: 'confirmed', severity: 'LOW', location: 'Tunnel Cam 2', visibility: 'N/A', speed: 'N/A', detected_at: new Date().toISOString(), details: 'Camera operating normally.' },
  { id: 'fb-8', type: 'fog', status: 'in_progress', severity: 'MEDIUM', location: 'Hill Pass', visibility: '40m', speed: '35 km/h', detected_at: new Date().toISOString(), details: 'Fog layer moving across pass; caution advised.' },
  { id: 'fb-9', type: 'pothole', status: 'open', severity: 'HIGH', location: 'Old Highway - Km 47', visibility: '25m', speed: '20 km/h', detected_at: new Date().toISOString(), details: 'Large crater; recommend reroute.' },
  { id: 'fb-10', type: 'camera', status: 'in_progress', severity: 'MEDIUM', location: 'Overpass Cam', visibility: 'N/A', speed: 'N/A', detected_at: new Date().toISOString(), details: 'Frame rate reduced; network latency observed.' },
]

export function AlertsPage() {
  const [apiBase] = useState(() => {
    const explicitBase = (import.meta.env.VITE_BACKEND_BASE as string | undefined)?.trim() ?? ''
    if (explicitBase) {
      return explicitBase
    }
    if (import.meta.env.DEV) {
      return 'http://127.0.0.1:8000'
    }
    return ''
  })
  
  const withBase = (path: string) => {
    const base = apiBase.replace(/\/$/, '')
    return base ? `${base}${path}` : path
  }

  const [alerts, setAlerts] = useState<AlertItem[]>(() => fallbackAlerts)
  const [severityFilter, setSeverityFilter] = useState<string>('all')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [loading, setLoading] = useState(false)

  const fetchAlerts = async () => {
    setLoading(true)
    try {
      const parseJsonResponse = async (response: Response, url: string) => {
        const contentType = response.headers.get('content-type') ?? ''
        if (!response.ok) {
          throw new Error(`Request failed (${response.status}) for ${url}`)
        }
        if (!contentType.toLowerCase().includes('application/json')) {
          throw new Error(`Expected JSON from ${url}`)
        }
        return response.json()
      }

      // 1. Fetch fog status
      const fogUrl = withBase('/api/fog/status/')
      const fogRes = await fetch(fogUrl)
      const fogData = await parseJsonResponse(fogRes, fogUrl)
      const fogItems = Array.isArray(fogData.items) ? fogData.items : []

      // 2. Fetch pothole status
      const potholeUrl = withBase('/api/pothole/status/')
      const potholeRes = await fetch(potholeUrl)
      const potholeData = await parseJsonResponse(potholeRes, potholeUrl)
      const potholeItems = Array.isArray(potholeData.items) ? potholeData.items : []

      const mappedAlerts: AlertItem[] = []

      fogItems.forEach((item: any) => {
        const prob = item.fog_probability ?? 0.0
        const level = item.fog_level ?? 'LOW'
        const risk = item.risk_score ?? 0.0
        const visibility = item.visibility_meters ?? 100.0

        if (prob > 0.4 || level === 'HIGH' || level === 'MEDIUM') {
          const speed = visibility < 30 ? '20 km/h' : visibility < 60 ? '30 km/h' : '50 km/h'
          
          mappedAlerts.push({
            id: `fog-${item.request_id || Math.random()}`,
            type: 'fog',
            status: risk > 0.6 ? 'confirmed' : 'monitoring',
            severity: level === 'HIGH' ? 'HIGH' : level === 'MEDIUM' ? 'MEDIUM' : 'LOW',
            location: item.source_id ? `Source: ${item.source_id}` : 'IP Camera',
            visibility: `${Math.round(visibility)}m`,
            speed: speed,
            detected_at: item.updated_at ? new Date(item.updated_at * 1000).toISOString() : new Date().toISOString(),
            details: `Dense fog detected (fused prob: ${prob.toFixed(2)}). Visibility is reduced to ${Math.round(visibility)}m. Risk score: ${risk.toFixed(2)}.`,
          })
        }
      })

      potholeItems.forEach((item: any) => {
        const count = item.pothole_count ?? 0
        const metrics = item.pothole_metrics || {}
        const risk = metrics.max_risk ?? 0.0
        const critical = metrics.critical_count ?? 0
        const high = metrics.high_count ?? 0

        if (count > 0) {
          const severity = risk > 0.75 || critical > 0 ? 'HIGH' : (risk > 0.45 || high > 0) ? 'MEDIUM' : 'LOW'
          const lat = item.coordinates?.lat
          const lng = item.coordinates?.lng
          const locationStr = (lat !== undefined && lng !== undefined) ? `NH75 - GPS: ${lat.toFixed(4)}, ${lng.toFixed(4)}` : `Source: ${item.source_id || 'IP Camera'}`

          mappedAlerts.push({
            id: `pothole-${item.request_id || Math.random()}`,
            type: 'pothole',
            status: severity === 'HIGH' ? 'open' : 'monitoring',
            severity: severity,
            location: locationStr,
            visibility: 'N/A',
            speed: severity === 'HIGH' ? '20 km/h' : '40 km/h',
            detected_at: item.created_at || new Date().toISOString(),
            details: `Detected ${count} pothole(s) in frame. Max risk: ${risk.toFixed(2)}. Critical: ${critical}, High: ${high}.`,
          })
        }
      })

      mappedAlerts.sort((a, b) => {
        return new Date(b.detected_at || '').getTime() - new Date(a.detected_at || '').getTime()
      })

      if (mappedAlerts.length > 0) {
        setAlerts(mappedAlerts)
      } else {
        setAlerts(fallbackAlerts)
      }
    } catch (e) {
      console.error('Failed to fetch real-time alerts', e)
      setAlerts(fallbackAlerts)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAlerts()
    const id = setInterval(fetchAlerts, 3000)
    return () => clearInterval(id)
  }, [])

  const severityOptions = useMemo(() => ['all', 'HIGH', 'MEDIUM', 'LOW'], [])

  const filtered = alerts.filter((a) => {
    if (severityFilter !== 'all' && a.severity !== severityFilter) return false
    if (typeFilter !== 'all' && a.type !== typeFilter) return false
    return true
  })

  return (
    <div className="page">
      <section>
        <BorderGlow className="panel glass">
          <div className="alert-toolbar">
            <ShinyText text="Real-time Alert Feed" className="text-xl font-bold" color="#ffffff" shineColor="#ffffff" />
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <select
                className="filter-select"
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
              >
                {severityOptions.map((s) => (
                  <option key={s} value={s}>
                    {s === 'all' ? 'Filter: All Severity' : s}
                  </option>
                ))}
              </select>

              <select className="filter-select" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
                <option value="all">Filter: All Types</option>
                <option value="pothole">Pothole</option>
                <option value="fog">Fog</option>
                <option value="camera">Camera</option>
              </select>
            </div>
          </div>

          <div className="alert-list">
            {loading && alerts.length === 0 ? (
              <div className="muted">Loading alerts…</div>
            ) : filtered.length === 0 ? (
              <div className="muted">No alerts match the selected filters.</div>
            ) : (
              filtered.map((alert) => (
                <BorderGlow
                  key={alert.id || `${alert.type}-${alert.location}-${alert.detected_at}`}
                  className={`alert-item ${String(alert.severity).toLowerCase()}`}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, color: '#ffffff' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <strong>
                          {alert.severity === 'HIGH' ? '🔴' : alert.severity === 'MEDIUM' ? '🟠' : '🟢'} {alert.severity}{' '}
                          {alert.type ? `· ${alert.type.toUpperCase()}` : ''}
                        </strong>
                        {alert.status && (
                          <span style={{ fontSize: 12, padding: '2px 8px', borderRadius: 12, background: 'rgba(255,255,255,0.08)', color: '#fff' }}>
                            {String(alert.status).toUpperCase()}
                          </span>
                        )}
                      </div>
                      <div>Location: {alert.location}</div>
                      {alert.visibility && alert.visibility !== 'N/A' && <div>Visibility: {alert.visibility}</div>}
                      {alert.speed && <div>Recommended Speed: {alert.speed}</div>}
                    </div>
                    <div style={{ textAlign: 'right', minWidth: 160, color: '#ffffff' }}>
                      {alert.detected_at && <div className="muted">{new Date(alert.detected_at).toLocaleString()}</div>}
                      {alert.details && <div className="small" style={{ marginTop: 4 }}>{alert.details}</div>}
                    </div>
                  </div>
                </BorderGlow>
              ))
            )}
          </div>
        </BorderGlow>
      </section>
    </div>
  )
}

