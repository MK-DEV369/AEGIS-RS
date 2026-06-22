import { motion } from 'framer-motion'
import { Circle, CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'
import BorderGlow from '@/components/BorderGlow'
import ShinyText from '@/components/ShinyText'
import { useEffect, useState, useMemo } from 'react'

function AreaChart({ data, color, gradientId }: { data: number[], color: string, gradientId: string }) {
  const width = 500
  const height = 150
  const padding = 20

  const points = useMemo(() => {
    if (data.length === 0) return ''
    const minVal = 0
    const maxVal = 1
    const xStep = (width - padding * 2) / Math.max(1, data.length - 1)
    
    return data.map((val, index) => {
      const x = padding + index * xStep
      const y = height - padding - ((val - minVal) / (maxVal - minVal)) * (height - padding * 2)
      return `${x},${y}`
    }).join(' ')
  }, [data, width, height, padding])

  const fillPoints = useMemo(() => {
    if (!points) return ''
    const xStep = (width - padding * 2) / Math.max(1, data.length - 1)
    const startX = padding
    const endX = padding + (data.length - 1) * xStep
    const baseY = height - padding
    return `${startX},${baseY} ${points} ${endX},${baseY}`
  }, [points, data, width, height, padding])

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: '100%', overflow: 'visible' }}>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.4" />
          <stop offset="100%" stopColor={color} stopOpacity="0.0" />
        </linearGradient>
      </defs>
      {/* Grid lines */}
      <line x1={padding} y1={padding} x2={width - padding} y2={padding} stroke="rgba(255,255,255,0.05)" strokeDasharray="3,3" />
      <line x1={padding} y1={height/2} x2={width - padding} y2={height/2} stroke="rgba(255,255,255,0.05)" strokeDasharray="3,3" />
      <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="rgba(255,255,255,0.1)" />
      
      {/* Area fill */}
      {fillPoints && <polygon points={fillPoints} fill={`url(#${gradientId})`} />}
      
      {/* Line path */}
      {points && <polyline points={points} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />}
      
      {/* Points */}
      {data.map((val, index) => {
        const xStep = (width - padding * 2) / Math.max(1, data.length - 1)
        const cx = padding + index * xStep
        const cy = height - padding - (val * (height - padding * 2))
        return (
          <circle key={index} cx={cx} cy={cy} r="4" fill="#1e1e24" stroke={color} strokeWidth="2" />
        )
      })}
    </svg>
  )
}

const mapCenter: [number, number] = [12.9716, 77.5946]

export function DashboardPage() {
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

  const [latestFog, setLatestFog] = useState<any>(null)
  const [latestPothole, setLatestPothole] = useState<any>(null)
  
  const [riskHistory, setRiskHistory] = useState<number[]>([0.65, 0.68, 0.72, 0.70, 0.73, 0.75, 0.72])
  const [fogHistory, setFogHistory] = useState<number[]>([0.70, 0.72, 0.75, 0.74, 0.76, 0.78, 0.78])

  useEffect(() => {
    let active = true
    let timerId = 0

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

    const fetchData = async () => {
      let currentFogProb = 0.78
      let currentRisk = 0.72
      let hasFog = false

      // 1. Fetch Fog status
      const fogStatusUrl = withBase('/api/fog/status/')
      try {
        const response = await fetch(fogStatusUrl)
        const payload = await parseJsonResponse(response, fogStatusUrl)
        const items = payload.items || []
        if (items.length > 0 && active) {
          const latest = items[0]
          setLatestFog(latest)
          currentFogProb = Number(latest.fog_probability ?? 0.78)
          currentRisk = Number(latest.risk_score ?? 0.72)
          hasFog = true
          
          setFogHistory(prev => [...prev, currentFogProb].slice(-10))
        }
      } catch (err) {
        console.error('Failed to fetch fog status on dashboard', err)
      }

      // 2. Fetch Pothole status
      const potholeStatusUrl = withBase('/api/pothole/status/')
      try {
        const response = await fetch(potholeStatusUrl)
        const payload = await parseJsonResponse(response, potholeStatusUrl)
        const items = payload.items || []
        if (items.length > 0 && active) {
          const latest = items[0]
          setLatestPothole(latest)
          if (!hasFog && latest.pothole_metrics?.max_risk) {
            currentRisk = Number(latest.pothole_metrics.max_risk)
          }
        }
      } catch (err) {
        console.error('Failed to fetch pothole status on dashboard', err)
      }

      if (active) {
        setRiskHistory(prev => [...prev, currentRisk].slice(-10))
        timerId = window.setTimeout(fetchData, 2000)
      }
    }

    fetchData()

    return () => {
      active = false
      window.clearTimeout(timerId)
    }
  }, [apiBase])

  const compositeRiskScore = latestFog?.risk_score ?? (latestPothole?.pothole_metrics?.max_risk ?? 0.72)
  const riskValueStr = `${Math.round(compositeRiskScore * 100)} / 100`
  const fogLevelStr = latestFog?.fog_level ? latestFog.fog_level.charAt(0).toUpperCase() + latestFog.fog_level.slice(1).toLowerCase() : 'Moderate'
  const visibilityStr = latestFog?.visibility_meters ? `${Math.round(latestFog.visibility_meters)} m` : '80 m'
  
  const potholeCountVal = latestPothole?.pothole_count ?? 0
  const activeAlertsStr = latestPothole ? String(potholeCountVal) : '5'

  const kpis = [
    { label: 'Risk Score', value: riskValueStr },
    { label: 'Fog Level', value: fogLevelStr },
    { label: 'Visibility', value: visibilityStr },
    { label: 'Active Alerts', value: activeAlertsStr },
  ]

  const breakdown = useMemo(() => {
    const fogVal = latestFog?.fog_probability ?? 0.45
    const potholeVal = latestPothole?.pothole_metrics?.max_risk ?? 0.25
    const trafficVal = 0.30
    
    const sum = fogVal + potholeVal + trafficVal
    return {
      fog: Math.round((fogVal / sum) * 100),
      pothole: Math.round((potholeVal / sum) * 100),
      traffic: Math.round((trafficVal / sum) * 100)
    }
  }, [latestFog, latestPothole])

  const fogProbDisplay = latestFog?.fog_probability ? latestFog.fog_probability.toFixed(3) : '0.78'

  const detectionsInfo = useMemo(() => {
    const detections = latestPothole?.detections
    if (detections && Array.isArray(detections.items) && detections.items.length > 0) {
      const items = detections.items
      const labels = items.map((i: any) => i.label ? i.label.charAt(0).toUpperCase() + i.label.slice(1) : 'Pothole')
      const confidences = items.map((i: any) => (i.confidence ?? 1.0).toFixed(2))
      return {
        objects: Array.from(new Set(labels)).join(', '),
        confidence: confidences.join(', ')
      }
    }
    return {
      objects: 'Pothole, Sign',
      confidence: '0.92, 0.84'
    }
  }, [latestPothole])

  return (
    <div className="page">
      <section className="kpi-grid">
        {kpis.map((kpi, index) => (
          <motion.article
            key={kpi.label}
            className=""
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.35 }}
            transition={{ duration: 0.35, delay: index * 0.06 }}
          >
            <BorderGlow className="kpi-card glass">
              <p>{kpi.label}</p>
              <strong>{kpi.value}</strong>
            </BorderGlow>
          </motion.article>
        ))}
      </section>

      <section className="grid dashboard-main">
        <motion.article
          className="map-panel"
          initial={{ opacity: 0, x: -18 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.45 }}
        >
          <BorderGlow className="panel glass">
            <ShinyText text="Interactive Map" className="text-xl font-bold mb-3" color="#ffffff" shineColor="#ffffff" />
            <div className="map-canvas">
              <div className="leaflet-shell">
                <MapContainer center={mapCenter} zoom={13} scrollWheelZoom style={{ height: '100%', width: '100%' }}>
                  <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />

                  <Circle center={[12.9697, 77.5972]} radius={350} pathOptions={{ color: '#22c55e', fillOpacity: 0.2 }}>
                    <Popup>Fog Cluster: Moderate Visibility Drop</Popup>
                  </Circle>

                  <CircleMarker center={[12.9741, 77.589]} radius={8} pathOptions={{ color: '#ef4444' }}>
                    <Popup>Pothole Zone A</Popup>
                  </CircleMarker>
                  <CircleMarker center={[12.9684, 77.601]} radius={8} pathOptions={{ color: '#ef4444' }}>
                    <Popup>Pothole Zone B</Popup>
                  </CircleMarker>

                  <CircleMarker center={[12.977, 77.5968]} radius={7} pathOptions={{ color: '#3b82f6' }}>
                    <Popup>Traffic Sign Region</Popup>
                  </CircleMarker>

                  <CircleMarker center={[12.9669, 77.5925]} radius={7} pathOptions={{ color: '#f59e0b' }}>
                    <Popup>Road Hump Section</Popup>
                  </CircleMarker>

                  <Circle center={[12.9716, 77.5946]} radius={800} pathOptions={{ color: '#a855f7', fillOpacity: 0.14 }}>
                    <Popup>Composite Risk Heat Zone</Popup>
                  </Circle>
                </MapContainer>
              </div>
            </div>
          </BorderGlow>
        </motion.article>

        <motion.aside
          className="insights-panel"
          initial={{ opacity: 0, x: 18 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.45, delay: 0.08 }}
        >
          <BorderGlow className="panel glass insights-panel">
            <ShinyText text="AI Insights Panel" className="text-xl font-bold mb-3" color="#ffffff" shineColor="#ffffff" />
            <div className="insight-block">
              <ShinyText text="AI Risk Breakdown" className="text-lg font-bold mb-2" color="#ffffff" shineColor="#ffffff" />
              <p>Fog: {breakdown.fog}%</p>
              <p>Traffic: {breakdown.traffic}%</p>
              <p>Potholes: {breakdown.pothole}%</p>
            </div>
            <div className="insight-block">
              <ShinyText text="Model Outputs" className="text-lg font-bold mb-2" color="#ffffff" shineColor="#ffffff" />
              <p>Fog Probability: {fogProbDisplay}</p>
              <p>Detected Objects: {detectionsInfo.objects}</p>
              <p>Confidence: {detectionsInfo.confidence}</p>
            </div>
          </BorderGlow>
        </motion.aside>
      </section>

      <section className="grid two-col">
        <motion.article
          className="chart-card"
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.25 }}
          transition={{ duration: 0.45, delay: 0.05 }}
        >
          <BorderGlow className="panel glass">
            <ShinyText text="Risk Over Time" className="text-xl font-bold mb-3" color="#ffffff" shineColor="#ffffff" />
            <div className="fake-chart" style={{ height: '150px', background: 'transparent' }}>
              <AreaChart data={riskHistory} color="#3b82f6" gradientId="riskGrad" />
            </div>
          </BorderGlow>
        </motion.article>

        <motion.article
          className="chart-card"
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.25 }}
          transition={{ duration: 0.45, delay: 0.12 }}
        >
          <BorderGlow className="panel glass">
            <ShinyText text="Fog Prediction Trend" className="text-xl font-bold mb-3" color="#ffffff" shineColor="#ffffff" />
            <div className="fake-chart" style={{ height: '150px', background: 'transparent' }}>
              <AreaChart data={fogHistory} color="#a855f7" gradientId="fogGrad" />
            </div>
          </BorderGlow>
        </motion.article>
      </section>
    </div>
  )
}

