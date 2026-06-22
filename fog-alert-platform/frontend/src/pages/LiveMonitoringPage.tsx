import { useEffect, useMemo, useState } from 'react'
import BorderGlow from '@/components/BorderGlow'
import ShinyText from '@/components/ShinyText'

type FrontendConfig = {
  default_sources?: {
    pothole?: string
    fog?: string
  }
  stream_fps?: number
  show_endpoints?: boolean
  backend_base_url?: string
  frontend_base_url?: string
  phone_base_urls?: {
    pothole?: string
    fog?: string
  }
}

type FogData = {
  fog_probability?: number
  fog_probability_smoothed?: number
  fog_label?: string
  fog_level?: string
  visibility_meters?: number
  contrast?: number
  risk_score?: number
}

type PotholeData = {
  max_risk?: number
  critical_count?: number
  high_count?: number
  detections_analyzed?: number
}

export function LiveMonitoringPage() {
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
  const [config, setConfig] = useState<FrontendConfig>({})
  const [potholeSourceId, setPotholeSourceId] = useState('phone_pothole_01')
  const [fogSourceId, setFogSourceId] = useState('phone_fog_01')
  const [potholeStatus, setPotholeStatus] = useState('Waiting for detections...')
  const [fogStatus, setFogStatus] = useState('Waiting for detections...')
  const [potholeCount, setPotholeCount] = useState(0)
  const [totalPotholes, setTotalPotholes] = useState(0)
  const [potholeData, setPotholeData] = useState<PotholeData>({})
  const [fogData, setFogData] = useState<FogData>({})
  const maxRisk = potholeData.max_risk ?? 0
  const [cameraUrl, setCameraUrl] = useState('http://192.168.1.21:6969')
  const [isPolling, setIsPolling] = useState(false)
  const withBase = (path: string) => {
    const base = apiBase.replace(/\/$/, '')
    return base ? `${base}${path}` : path
  }

  const parseJsonResponse = async (response: Response, url: string) => {
    const contentType = response.headers.get('content-type') ?? ''
    if (!response.ok) {
      throw new Error(`Request failed (${response.status}) for ${url}`)
    }
    if (!contentType.toLowerCase().includes('application/json')) {
      const preview = (await response.text()).slice(0, 120)
      throw new Error(`Expected JSON from ${url}, got '${contentType || 'unknown'}'. Preview: ${preview}`)
    }
    return response.json()
  }

  const startCombinedPolling = async () => {
    const potholeSource = potholeSourceId.trim() || 'phone_pothole_01'
    const fogSource = fogSourceId.trim() || 'phone_fog_01'
    const requestUrl = withBase('/api/combined/camera/start/')
    
    // Retrieve laptop browser GPS coordinates
    let latitude: number | null = null
    let longitude: number | null = null
    
    if (navigator.geolocation) {
      try {
        const position = await new Promise<GeolocationPosition>((resolve, reject) => {
          navigator.geolocation.getCurrentPosition(resolve, reject, {
            enableHighAccuracy: true,
            timeout: 5000,
            maximumAge: 0
          })
        });
        latitude = position.coords.latitude
        longitude = position.coords.longitude
        console.debug('[monitoring] Laptop browser GPS acquired:', latitude, longitude)
      } catch (geoError) {
        console.warn('[monitoring] Could not retrieve laptop browser GPS, starting without coordinates:', geoError)
      }
    } else {
      console.warn('[monitoring] Geolocation is not supported by this browser')
    }

    try {
      const formData = new FormData()
      formData.append('camera_base', cameraUrl.trim())
      formData.append('pothole_source_id', potholeSource)
      formData.append('fog_source_id', fogSource)
      formData.append('interval', '1.0')
      
      if (latitude !== null && longitude !== null) {
        formData.append('latitude', String(latitude))
        formData.append('longitude', String(longitude))
      }

      const response = await fetch(requestUrl, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(errorText || `Failed to start combined camera polling (${response.status})`)
      }

      setIsPolling(true)
      setPotholeStatus('Backend combined camera polling started. Waiting for frames...')
      setFogStatus('Backend combined camera polling started. Waiting for frames...')
    } catch (error) {
      console.error('[monitoring] start combined camera polling failed', { requestUrl, error })
      const msg = error instanceof Error ? error.message : 'Failed to start combined camera polling'
      setPotholeStatus(msg)
      setFogStatus(msg)
    }
  }

  const stopCombinedPolling = async () => {
    const potholeSource = potholeSourceId.trim() || 'phone_pothole_01'
    const fogSource = fogSourceId.trim() || 'phone_fog_01'
    const requestUrl = withBase('/api/combined/camera/stop/')
    try {
      const formData = new FormData()
      formData.append('pothole_source_id', potholeSource)
      formData.append('fog_source_id', fogSource)

      const response = await fetch(requestUrl, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(errorText || `Failed to stop combined camera polling (${response.status})`)
      }

      setIsPolling(false)
      setPotholeStatus('Backend combined camera polling stopped.')
      setFogStatus('Backend combined camera polling stopped.')
    } catch (error) {
      console.error('[monitoring] stop combined camera polling failed', { requestUrl, error })
      const msg = error instanceof Error ? error.message : 'Failed to stop combined camera polling'
      setPotholeStatus(msg)
      setFogStatus(msg)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    const configUrl = withBase('/api/frontend/config/')
    fetch(configUrl, { signal: controller.signal })
      .then((response) => parseJsonResponse(response, configUrl))
      .then((payload: FrontendConfig) => {
        console.debug('[monitoring] frontend config payload', payload)
        setConfig(payload)
        const pothole = payload.default_sources?.pothole?.trim()
        const fog = payload.default_sources?.fog?.trim()
        if (pothole) {
          setPotholeSourceId(pothole)
        }
        if (fog) {
          setFogSourceId(fog)
        }
      })
      .catch((error) => {
        if (controller.signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) {
          return
        }
        console.error('[monitoring] config fetch failed', { configUrl, error })
        // Keep local defaults when backend config is unavailable.
      })
    return () => controller.abort()
  }, [apiBase])

  useEffect(() => {
    const controller = new AbortController()
    let timerId = 0

    const pollStatus = async () => {
      let nextDelayMs = 5000

      const query = new URLSearchParams()
      if (potholeSourceId.trim()) {
        query.set('source_id', potholeSourceId.trim())
      }

      const potholeStatusUrl = withBase(`/api/pothole/status/?${query.toString()}`)
      try {
        const response = await fetch(potholeStatusUrl, {
          signal: controller.signal,
        })
        const payload = await parseJsonResponse(response, potholeStatusUrl)
        const hasRows = Array.isArray(payload.items) && payload.items.length > 0
        if (hasRows) {
          nextDelayMs = 2000
        }

          const latest = Array.isArray(payload.items) && payload.items.length > 0 ? payload.items[0] : null
          setPotholeCount(latest?.pothole_count ?? 0)
          setTotalPotholes(latest?.total_potholes ?? 0)
          
          const metrics = latest?.pothole_metrics ?? {}
          const potholeInfo: PotholeData = {
            max_risk: Number(metrics.max_risk ?? 0),
            critical_count: Number(metrics.critical_count ?? 0),
            high_count: Number(metrics.high_count ?? 0),
            detections_analyzed: Number(metrics.detections_analyzed ?? 0),
          }
          setPotholeData(potholeInfo)
          
          const coordinates = latest?.coordinates
          if (coordinates && typeof coordinates === 'object') {
            const lat = (coordinates as { lat?: number | string }).lat
            const lng = (coordinates as { lng?: number | string }).lng
            const summaryParts = [
              `Frames: ${payload.count ?? 0}`,
              `Risk: ${potholeInfo.max_risk?.toFixed(3) ?? '0'}`,
              `Critical: ${potholeInfo.critical_count ?? 0}`,
              `High: ${potholeInfo.high_count ?? 0}`,
              `Current: ${latest?.pothole_count ?? 0}`,
            ]
            if (lat !== undefined || lng !== undefined) {
              summaryParts.push(`GPS: ${lat ?? '-'}, ${lng ?? '-'}`)
            }
            setPotholeStatus(summaryParts.join(' | '))
          } else {
            if ((payload.count ?? 0) === 0) {
              setPotholeStatus('No pothole frames yet. Send frames to /api/pothole/predict/ to start live updates.')
            } else {
              setPotholeStatus(`Frames: ${payload.count ?? 0} | Risk: ${potholeInfo.max_risk?.toFixed(3) ?? '0'} | Critical: ${potholeInfo.critical_count ?? 0} | High: ${potholeInfo.high_count ?? 0}`)
            }
          }
      } catch (error) {
        if (!controller.signal.aborted && !(error instanceof DOMException && error.name === 'AbortError')) {
          console.error('[monitoring] pothole status fetch failed', { potholeStatusUrl, error })
          setPotholeStatus(error instanceof Error ? error.message : 'Unable to load pothole status')
        }
      }

      const fogQuery = new URLSearchParams()
      if (fogSourceId.trim()) {
        fogQuery.set('source_id', fogSourceId.trim())
      }
      const fogStatusUrl = withBase(`/api/fog/status/?${fogQuery.toString()}`)
      try {
        const response = await fetch(fogStatusUrl, {
          signal: controller.signal,
        })
        const payload = await parseJsonResponse(response, fogStatusUrl)
        const hasRows = Array.isArray(payload.items) && payload.items.length > 0
        if (hasRows) {
          nextDelayMs = 2000
        }

          const latest = Array.isArray(payload.items) && payload.items.length > 0 ? payload.items[0] : null
          const fogInfo: FogData = {
            fog_probability: Number(latest?.fog_probability ?? 0),
            fog_probability_smoothed: Number(latest?.fog_probability_smoothed ?? Number(latest?.fog_probability ?? 0)),
            fog_label: String(latest?.fog_label ?? '-'),
            fog_level: String(latest?.fog_level ?? '-'),
            visibility_meters: Number(latest?.visibility_meters ?? 0),
            contrast: Number(latest?.contrast ?? 0),
            risk_score: Number(latest?.risk_score ?? 0),
          }
          setFogData(fogInfo)
          
          const statusParts = [
            `Frames: ${payload.count ?? 0}`,
            `Level: ${fogInfo.fog_level}`,
            `Prob: ${fogInfo.fog_probability?.toFixed(3) ?? '0'}`,
            `Smoothed: ${fogInfo.fog_probability_smoothed?.toFixed(3) ?? '0'}`,
            `Visibility: ${fogInfo.visibility_meters?.toFixed(1) ?? '0'}m`,
            `Risk: ${fogInfo.risk_score?.toFixed(3) ?? '0'}`,
          ]
          if ((payload.count ?? 0) === 0) {
            setFogStatus('No fog frames yet. Send frames to /api/fog/predict/ to start live updates.')
          } else {
            setFogStatus(statusParts.join(' | '))
          }
      } catch (error) {
        if (!controller.signal.aborted && !(error instanceof DOMException && error.name === 'AbortError')) {
          console.error('[monitoring] fog status fetch failed', { fogStatusUrl, error })
          setFogStatus(error instanceof Error ? error.message : 'Unable to load fog status')
        }
      }

      if (!controller.signal.aborted) {
        timerId = window.setTimeout(pollStatus, nextDelayMs)
      }
    }

    const syncPollingStatus = async () => {
      const potholeSource = potholeSourceId.trim() || 'phone_pothole_01'
      const fogSource = fogSourceId.trim() || 'phone_fog_01'
      const pollStatusUrl = withBase(
        `/api/combined/camera/poll_status/?pothole_source_id=${encodeURIComponent(potholeSource)}&fog_source_id=${encodeURIComponent(fogSource)}`
      )
      try {
        const response = await fetch(pollStatusUrl, { signal: controller.signal })
        const payload = await parseJsonResponse(response, pollStatusUrl)
        setIsPolling(!!payload.running)
      } catch (error) {
        if (!controller.signal.aborted && !(error instanceof DOMException && error.name === 'AbortError')) {
          console.debug('[monitoring] combined camera poll status unavailable', { pollStatusUrl, error })
        }
      }
    }

    pollStatus()
    syncPollingStatus()

    return () => {
      controller.abort()
      window.clearTimeout(timerId)
    }
  }, [apiBase, fogSourceId, potholeSourceId])

  const endpoints = useMemo(() => {
    const fps = Number(config.stream_fps ?? 3)
    const safeFps = Number.isFinite(fps) && fps > 0 ? fps : 3
    const potholeSource = potholeSourceId.trim() || 'phone_pothole_01'
    const fogSource = fogSourceId.trim() || 'phone_fog_01'
    return {
      potholeStream: withBase(`/api/pothole/stream/?source_id=${encodeURIComponent(potholeSource)}&fps=${safeFps}`),
      fogStream: withBase(`/api/fog/stream/?source_id=${encodeURIComponent(fogSource)}&fps=${safeFps}`),
    }
  }, [apiBase, config.stream_fps, fogSourceId, potholeSourceId])

  return (
    <div className="page">
      <BorderGlow className="panel glass mb-6" style={{ marginBottom: '20px', padding: '20px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px', alignItems: 'end' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="camera-url" style={{ fontWeight: 'bold', fontSize: '0.95em' }}>Camera URL</label>
            <input
              id="camera-url"
              className="phone-input"
              value={cameraUrl}
              onChange={(event) => setCameraUrl(event.target.value)}
              placeholder="http://192.168.1.21:6969"
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="pothole-source-id" style={{ fontWeight: 'bold', fontSize: '0.95em' }}>Pothole Source ID</label>
            <input
              id="pothole-source-id"
              className="phone-input"
              value={potholeSourceId}
              onChange={(event) => setPotholeSourceId(event.target.value)}
              placeholder="phone_pothole_01"
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="fog-source-id" style={{ fontWeight: 'bold', fontSize: '0.95em' }}>Fog Source ID</label>
            <input
              id="fog-source-id"
              className="phone-input"
              value={fogSourceId}
              onChange={(event) => setFogSourceId(event.target.value)}
              placeholder="phone_fog_01"
            />
          </div>
        </div>
      </BorderGlow>

      <section className="grid one-col" style={{ gridTemplateColumns: '1fr', marginBottom: '20px' }}>
        <article className="video-panel" style={{ maxWidth: '960px', margin: '0 auto', width: '100%' }}>
          <BorderGlow className="panel glass">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px', flexWrap: 'wrap', gap: '10px' }}>
              <ShinyText text="AEGIS Active ADAS Monitor" className="text-xl font-bold" color="#ffffff" shineColor="#ffffff" />
              <div style={{ display: 'flex', gap: '8px', fontSize: '0.85em', opacity: 0.9 }}>
                <span className="chip" style={{ background: 'rgba(0,255,255,0.12)', borderColor: 'rgba(0,255,255,0.25)', padding: '4px 10px', borderRadius: '6px' }}>
                  Pothole Stream: <strong>{potholeSourceId}</strong>
                </span>
                <span className="chip" style={{ background: 'rgba(94,234,212,0.12)', borderColor: 'rgba(94,234,212,0.25)', padding: '4px 10px', borderRadius: '6px' }}>
                  Fog Stream: <strong>{fogSourceId}</strong>
                </span>
              </div>
            </div>

            <div className="live-video-wrap pulse-border" style={{ minHeight: '520px', maxHeight: '720px', width: '100%', position: 'relative', overflow: 'hidden' }}>
              <img src={endpoints.potholeStream} alt="AEGIS Active ADAS Monitor Stream" className="live-video" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '20px', padding: '15px', background: 'rgba(0,0,0,0.18)', borderRadius: '10px', marginTop: '15px', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.95em', marginBottom: '4px' }}>
                  <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: isPolling ? '#4CAF50' : '#f44336', display: 'inline-block', boxShadow: isPolling ? '0 0 10px #4CAF50' : 'none' }}></span>
                  <strong>System Status:</strong> {isPolling ? 'ACTIVE POLLED MONITORING' : 'STANDBY'}
                </div>
                <p className="control-status" style={{ fontSize: '0.88em', opacity: 0.9 }}>
                  <strong>Pothole telemetry:</strong> {potholeStatus}
                </p>
                <p className="control-status" style={{ fontSize: '0.88em', opacity: 0.9 }}>
                  <strong>Fog telemetry:</strong> {fogStatus}
                </p>
              </div>
              <div style={{ minWidth: '160px' }}>
                {!isPolling ? (
                  <button
                    type="button"
                    onClick={startCombinedPolling}
                    style={{ width: '100%', background: '#4CAF50', color: 'white', border: 'none', padding: '12px 25px', borderRadius: '10px', cursor: 'pointer', fontWeight: 'bold', fontSize: '1.05em', transition: 'background-color 0.2s', boxShadow: '0 4px 12px rgba(76,175,80,0.3)' }}
                  >
                    Start AI
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={stopCombinedPolling}
                    style={{ width: '100%', background: '#f44336', color: 'white', border: 'none', padding: '12px 25px', borderRadius: '10px', cursor: 'pointer', fontWeight: 'bold', fontSize: '1.05em', transition: 'background-color 0.2s', boxShadow: '0 4px 12px rgba(244,67,54,0.3)' }}
                  >
                    Stop AI
                  </button>
                )}
              </div>
            </div>
          </BorderGlow>
        </article>
      </section>

      <section className="grid two-col">
        <article>
          <BorderGlow className="panel glass insights-panel">
            <ShinyText text="Pothole Analysis" className="text-xl font-bold mb-3" color="#ffffff" shineColor="#ffffff" />
            <div className="analysis-metrics">
              <div className="metric-grid">
                <div className="metric-item">
                  <span className="label">Max Risk</span>
                  <span className={`value ${maxRisk > 0.8 ? 'critical' : maxRisk > 0.5 ? 'high' : 'normal'}`}>
                    {maxRisk.toFixed(3)}
                  </span>
                </div>
                <div className="metric-item">
                  <span className="label">Critical</span>
                  <span className="value">{potholeData.critical_count ?? 0}</span>
                </div>
                <div className="metric-item">
                  <span className="label">High</span>
                  <span className="value">{potholeData.high_count ?? 0}</span>
                </div>
                <div className="metric-item">
                  <span className="label">Analyzed</span>
                  <span className="value">{potholeData.detections_analyzed ?? 0}</span>
                </div>
              </div>
            </div>
            <div className="insight-block">
              <p>Current Frame: {potholeCount} potholes</p>
              <p>Total Detected: {totalPotholes} potholes</p>
              <p className="text-sm text-gray-400">Location: {
                potholeStatus.includes('GPS') 
                  ? potholeStatus.split('GPS:')[1]?.trim()
                  : 'Unknown'
              }</p>
            </div>
          </BorderGlow>
        </article>

        <article>
          <BorderGlow className="panel glass">
            <ShinyText text="Fog Analysis" className="text-xl font-bold mb-3" color="#ffffff" shineColor="#ffffff" />
            <div className="insight-block">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.9em' }}>
                <p><strong>Level:</strong> <span style={{ color: fogData.fog_level === 'HIGH' ? '#ff4444' : fogData.fog_level === 'MEDIUM' ? '#ffaa00' : '#44ff44' }}>{fogData.fog_level ?? '-'}</span></p>
                <p><strong>Probability:</strong> {fogData.fog_probability?.toFixed(3) ?? '-'}</p>
                <p><strong>Smoothed:</strong> {fogData.fog_probability_smoothed?.toFixed(3) ?? '-'}</p>
                <p><strong>Visibility:</strong> {fogData.visibility_meters?.toFixed(1) ?? '-'}m</p>
                <p><strong>Contrast:</strong> {fogData.contrast?.toFixed(3) ?? '-'}</p>
                <p><strong>Risk Score:</strong> {fogData.risk_score?.toFixed(3) ?? '-'}</p>
              </div>
              <p style={{ marginTop: '8px', fontSize: '0.85em', opacity: 0.8 }}>{fogStatus}</p>
              {config.show_endpoints ? <p style={{ fontSize: '0.8em', opacity: 0.6 }}>Stream: {endpoints.fogStream}</p> : null}
            </div>
          </BorderGlow>
        </article>
      </section>
    </div>
  )
}
