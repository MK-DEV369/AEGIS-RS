import { useState, useEffect } from 'react'
import { Circle, CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet'
import BorderGlow from '@/components/BorderGlow'
import ShinyText from '@/components/ShinyText'

type LayerKey = 'fog' | 'potholes' | 'signs' | 'humps' | 'risk' | 'rsu'

const layerLabels: Record<LayerKey, string> = {
  fog: 'Fog Detections',
  potholes: 'Pothole Zones',
  signs: 'Traffic Signs',
  humps: 'Road Humps',
  risk: 'Composite Risk Heatmap',
  rsu: '📡 RSU ESP-NOW Warnings',
}

// Leaflet recentering component helper
function ChangeView({ center }: { center: [number, number] }) {
  const map = useMap()
  useEffect(() => {
    map.setView(center, map.getZoom())
  }, [center, map])
  return null
}

export function LiveMapPage() {
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

  // Layer toggling states
  const [activeLayers, setActiveLayers] = useState<Record<LayerKey, boolean>>({
    fog: true,
    potholes: true,
    signs: true,
    humps: true,
    risk: true,
    rsu: true,
  })

  // Dynamic Map coordinates and zoom
  const [mapCenter, setMapCenter] = useState<[number, number]>([12.9242853, 77.4996733]) // Default to active Kengeri test site

  // Simulation controls state
  const [simCoords, setSimCoords] = useState({ lat: '12.9242853', lng: '77.4996733' })
  const [simSeverity, setSimSeverity] = useState('MEDIUM')
  const [simFogLevel, setSimFogLevel] = useState('MEDIUM')
  const [simRisk, setSimRisk] = useState('0.65')
  const [triggerStatus, setTriggerStatus] = useState('')

  // Database polled data
  const [potholesList, setPotholesList] = useState<any[]>([])
  const [fogList, setFogList] = useState<any[]>([])
  const [telemetryList, setTelemetryList] = useState<any[]>([])

  const toggleLayer = (layer: LayerKey) => {
    setActiveLayers((prev) => ({ ...prev, [layer]: !prev[layer] }))
  }

  // Polling data function
  const fetchAllData = async () => {
    try {
      // 1. Fetch pothole statuses
      const potholeUrl = withBase('/api/pothole/status/')
      const potholeRes = await fetch(potholeUrl)
      if (potholeRes.ok) {
        const data = await potholeRes.json()
        if (data && Array.isArray(data.items)) {
          setPotholesList(data.items)
        }
      }

      // 2. Fetch fog statuses
      const fogUrl = withBase('/api/fog/status/')
      const fogRes = await fetch(fogUrl)
      if (fogRes.ok) {
        const data = await fogRes.json()
        if (data && Array.isArray(data.items)) {
          setFogList(data.items)
        }
      }

      // 3. Fetch telemetry/RSU logs
      const telUrl = withBase('/api/telemetry/latest/')
      const telRes = await fetch(telUrl)
      if (telRes.ok) {
        const data = await telRes.json()
        if (data && Array.isArray(data.items)) {
          setTelemetryList(data.items)
        }
      }
    } catch (err) {
      console.error('Error polling map data:', err)
    }
  }

  // Set up polling loop
  useEffect(() => {
    fetchAllData()
    const interval = setInterval(fetchAllData, 2000)
    return () => clearInterval(interval)
  }, [apiBase])

  // Simulation Triggers
  const triggerPotholeSim = async () => {
    const lat = parseFloat(simCoords.lat)
    const lng = parseFloat(simCoords.lng)
    if (isNaN(lat) || isNaN(lng)) {
      setTriggerStatus('❌ Invalid coordinates')
      return
    }

    setTriggerStatus('⌛ Registering pothole alert on backend...')
    try {
      const res = await fetch(withBase('/api/simulate/pothole/'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lat: lat,
          lng: lng,
          severity: simSeverity,
          source_id: 'OBU-01'
        })
      })
      const data = await res.json()
      if (data.ok) {
        setTriggerStatus('📡 Sent to Vehicle OBU! Broadcasting via ESP-NOW...')
        setMapCenter([lat, lng])
        fetchAllData()
      } else {
        setTriggerStatus(`❌ Backend error: ${data.error || 'Failed'}`)
      }
    } catch (err: any) {
      setTriggerStatus(`❌ Network error: ${err.message}`)
    }
  }

  const triggerFogSim = async () => {
    const lat = parseFloat(simCoords.lat)
    const lng = parseFloat(simCoords.lng)
    const risk = parseFloat(simRisk)
    if (isNaN(lat) || isNaN(lng) || isNaN(risk)) {
      setTriggerStatus('❌ Invalid inputs')
      return
    }

    setTriggerStatus('⌛ Registering fog alert on backend...')
    try {
      const res = await fetch(withBase('/api/simulate/fog/'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lat: lat,
          lng: lng,
          fog_level: simFogLevel,
          risk_score: risk,
          source_id: 'OBU-01'
        })
      })
      const data = await res.json()
      if (data.ok) {
        setTriggerStatus('📡 Sent to Vehicle OBU! Broadcasting via ESP-NOW...')
        setMapCenter([lat, lng])
        fetchAllData()
      } else {
        setTriggerStatus(`❌ Backend error: ${data.error || 'Failed'}`)
      }
    } catch (err: any) {
      setTriggerStatus(`❌ Network error: ${err.message}`)
    }
  }

  return (
    <div className="page">
      <section className="grid dashboard-main">
        {/* Map Display Column */}
        <article>
          <BorderGlow className="panel glass" style={{ height: '100%', padding: '0px', overflow: 'hidden' }}>
            <div className="map-canvas live-map fullscreen" style={{ margin: 0, height: '100%', minHeight: '620px' }}>
              <div className="leaflet-shell">
                <MapContainer center={mapCenter} zoom={15} scrollWheelZoom style={{ height: '100%', width: '100%' }}>
                  <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />
                  <ChangeView center={mapCenter} />

                  {/* 1. Static Road signs and humps mock overlays */}
                  {activeLayers.signs && (
                    <CircleMarker center={[12.9265, 77.4985]} radius={7} pathOptions={{ color: '#3b82f6', fillColor: '#3b82f6', fillOpacity: 0.5 }}>
                      <Popup>Static Traffic Sign Region</Popup>
                    </CircleMarker>
                  )}

                  {activeLayers.humps && (
                    <CircleMarker center={[12.9228, 77.5012]} radius={7} pathOptions={{ color: '#f59e0b', fillColor: '#f59e0b', fillOpacity: 0.5 }}>
                      <Popup>Static Road Hump Section</Popup>
                    </CircleMarker>
                  )}

                  {activeLayers.risk && (
                    <Circle center={[12.9242853, 77.4996733]} radius={500} pathOptions={{ color: '#a855f7', fillOpacity: 0.08 }}>
                      <Popup>Active ADAS Risk Alert Sector</Popup>
                    </Circle>
                  )}

                  {/* 2. Dynamic Potholes from YOLO backend */}
                  {activeLayers.potholes && potholesList.map((item) => {
                    const lat = item.coordinates?.lat
                    const lng = item.coordinates?.lng
                    if (!lat || !lng) return null
                    return (
                      <CircleMarker
                        key={`pot-${item.id}`}
                        center={[lat, lng]}
                        radius={9}
                        pathOptions={{ color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.7 }}
                      >
                        <Popup>
                          <div style={{ color: '#000' }}>
                            <strong style={{ color: '#ef4444' }}>⚠️ Pothole Detected</strong><br />
                            <strong>Severity:</strong> {item.pothole_metrics?.worst_severity || 'MEDIUM'}<br />
                            <strong>Source:</strong> {item.source_id}<br />
                            <strong>Date:</strong> {new Date(item.created_at).toLocaleString()}<br />
                            <strong>GPS:</strong> {lat.toFixed(6)}, {lng.toFixed(6)}
                          </div>
                        </Popup>
                      </CircleMarker>
                    )
                  })}

                  {/* 3. Dynamic Fog alert zones from XGBoost backend */}
                  {activeLayers.fog && fogList.map((item) => {
                    const lat = item.coordinates?.lat
                    const lng = item.coordinates?.lng
                    if (!lat || !lng) return null
                    const radius = item.visibility_meters ? Math.max(100, 300 - item.visibility_meters) : 250
                    return (
                      <Circle
                        key={`fog-${item.request_id || item.updated_at}`}
                        center={[lat, lng]}
                        radius={radius}
                        pathOptions={{ color: '#10b981', fillColor: '#10b981', fillOpacity: 0.25 }}
                      >
                        <Popup>
                          <div style={{ color: '#000' }}>
                            <strong style={{ color: '#10b981' }}>🌫️ Fog Detected</strong><br />
                            <strong>Level:</strong> {item.fog_level || 'MEDIUM'}<br />
                            <strong>Visibility:</strong> {item.visibility_meters?.toFixed(0)}m<br />
                            <strong>Risk Index:</strong> {item.risk_score?.toFixed(2)}<br />
                            <strong>Source:</strong> {item.source_id}<br />
                            <strong>GPS:</strong> {lat.toFixed(6)}, {lng.toFixed(6)}
                          </div>
                        </Popup>
                      </Circle>
                    )
                  })}

                  {/* 4. Dynamic ESP32 Telemetry / RSU warnings received via ESP-NOW */}
                  {activeLayers.rsu && telemetryList.map((item) => {
                    const lat = item.lat
                    const lng = item.lng
                    if (!lat || !lng) return null

                    const isPothole = item.event === 'RSU_Pothole'
                    const markerColor = isPothole ? '#8b5cf6' : '#2563eb' // Purple for pothole, Blue for fog
                    const markerFill = isPothole ? '#c084fc' : '#60a5fa'
                    
                    return (
                      <CircleMarker
                        key={`rsu-${item.source_id || item.updated_at}`}
                        center={[lat, lng]}
                        radius={13}
                        pathOptions={{ color: markerColor, fillColor: markerFill, fillOpacity: 0.8, weight: 3, dashArray: '2, 2' }}
                      >
                        <Popup>
                          <div style={{ color: '#000' }}>
                            <strong style={{ color: markerColor }}>📡 RSU Recv Warning (ESP-NOW)</strong><br />
                            <strong>Hazard:</strong> {isPothole ? 'POTHOLE' : 'FOG'}<br />
                            <strong>Source Node:</strong> OBU-01<br />
                            <strong>Status:</strong> {item.status || 'DISSEMINATED'}<br />
                            <strong>Node Speed:</strong> {item.speed_kmph} km/h<br />
                            <strong>Received At:</strong> {new Date(item.updated_at * 1000).toLocaleTimeString()}
                          </div>
                        </Popup>
                      </CircleMarker>
                    )
                  })}
                </MapContainer>
              </div>
            </div>
          </BorderGlow>
        </article>

        {/* Sidebar Controls Column */}
        <article className="grid" style={{ gap: '16px', alignContent: 'start' }}>
          {/* Map layers list */}
          <BorderGlow className="panel glass">
            <ShinyText text="Map Layers" className="text-xl font-bold mb-3" color="#ffffff" shineColor="#ffffff" />
            <div className="stack-grid" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {(Object.keys(layerLabels) as LayerKey[]).map((layerKey) => (
                <label key={layerKey} className="chip checkbox-chip" style={{ width: '100%', justifyContent: 'flex-start', margin: 0, padding: '8px 12px' }}>
                  <input
                    type="checkbox"
                    checked={activeLayers[layerKey]}
                    onChange={() => toggleLayer(layerKey)}
                    style={{ marginRight: '8px' }}
                  />
                  {layerLabels[layerKey]}
                </label>
              ))}
            </div>
          </BorderGlow>

          {/* V2I2V Simulator panel */}
          <BorderGlow className="panel glass">
            <ShinyText text="OBU V2X Simulator" className="text-xl font-bold mb-3" color="#ffffff" shineColor="#ffffff" />
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '0.85em', opacity: 0.8, display: 'block', marginBottom: '4px' }}>Latitude</label>
                <input
                  type="text"
                  value={simCoords.lat}
                  onChange={(e) => setSimCoords(prev => ({ ...prev, lat: e.target.value }))}
                  style={{ width: '100%', background: 'rgba(255,255,255,0.05)', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', padding: '8px', borderRadius: '6px' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.85em', opacity: 0.8, display: 'block', marginBottom: '4px' }}>Longitude</label>
                <input
                  type="text"
                  value={simCoords.lng}
                  onChange={(e) => setSimCoords(prev => ({ ...prev, lng: e.target.value }))}
                  style={{ width: '100%', background: 'rgba(255,255,255,0.05)', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', padding: '8px', borderRadius: '6px' }}
                />
              </div>

              <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '10px' }}>
                <label style={{ fontSize: '0.85em', opacity: 0.8, display: 'block', marginBottom: '4px' }}>Pothole Severity</label>
                <select
                  value={simSeverity}
                  onChange={(e) => setSimSeverity(e.target.value)}
                  style={{ width: '100%', background: 'rgba(15,19,32,0.95)', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', padding: '8px', borderRadius: '6px', cursor: 'pointer' }}
                >
                  <option value="LOW">LOW</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="HIGH">HIGH</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
                <button
                  type="button"
                  onClick={triggerPotholeSim}
                  style={{ marginTop: '8px', width: '100%', background: '#ef4444', color: '#fff', border: 'none', padding: '10px', borderRadius: '8px', fontWeight: 'bold', cursor: 'pointer', boxShadow: '0 4px 8px rgba(239,68,68,0.2)' }}
                >
                  Trigger Pothole (OBU)
                </button>
              </div>

              <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '10px' }}>
                <label style={{ fontSize: '0.85em', opacity: 0.8, display: 'block', marginBottom: '4px' }}>Fog Level / Risk</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <select
                    value={simFogLevel}
                    onChange={(e) => setSimFogLevel(e.target.value)}
                    style={{ flex: 1, background: 'rgba(15,19,32,0.95)', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', padding: '8px', borderRadius: '6px', cursor: 'pointer' }}
                  >
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                    <option value="CRITICAL">CRITICAL</option>
                  </select>
                  <input
                    type="number"
                    step="0.05"
                    min="0"
                    max="1"
                    value={simRisk}
                    onChange={(e) => setSimRisk(e.target.value)}
                    style={{ width: '80px', background: 'rgba(255,255,255,0.05)', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', padding: '8px', borderRadius: '6px' }}
                    placeholder="Risk"
                  />
                </div>
                <button
                  type="button"
                  onClick={triggerFogSim}
                  style={{ marginTop: '8px', width: '100%', background: '#10b981', color: '#fff', border: 'none', padding: '10px', borderRadius: '8px', fontWeight: 'bold', cursor: 'pointer', boxShadow: '0 4px 8px rgba(16,185,129,0.2)' }}
                >
                  Trigger Fog Alert (OBU)
                </button>
              </div>

              <button
                type="button"
                onClick={() => setMapCenter([12.9242853, 77.4996733])}
                style={{ width: '100%', background: 'transparent', color: '#3b82f6', border: '1px dashed #3b82f6', padding: '8px', borderRadius: '8px', cursor: 'pointer', fontSize: '0.9em', fontWeight: '500', transition: 'all 0.2s' }}
              >
                Center on Test Area
              </button>

              {triggerStatus && (
                <div style={{ padding: '8px 12px', background: 'rgba(255,255,255,0.05)', borderLeft: '3px solid #3b82f6', borderRadius: '4px', fontSize: '0.85em', color: '#e5e7eb', marginTop: '4px', whiteSpace: 'pre-wrap' }}>
                  {triggerStatus}
                </div>
              )}
            </div>
          </BorderGlow>
        </article>
      </section>
    </div>
  )
}
