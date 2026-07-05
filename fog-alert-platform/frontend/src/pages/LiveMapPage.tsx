import { useState, useEffect, useRef } from 'react'
import { Circle, CircleMarker, MapContainer, Marker, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import BorderGlow from '@/components/BorderGlow'
import ShinyText from '@/components/ShinyText'
import L from 'leaflet'

type LayerKey = 'fog' | 'potholes' | 'signs' | 'humps' | 'risk' | 'rsu'

const layerLabels: Record<LayerKey, string> = {
  fog: 'Fog Detections',
  potholes: 'Pothole Zones',
  signs: 'Traffic Signs',
  humps: 'Road Humps',
  risk: 'Composite Risk Heatmap',
  rsu: 'RSU ESP-NOW Warnings',
}

const createSignIcon = (label: string, cat: string) => {
  let html = ''
  
  if (label.startsWith('Speed Limit')) {
    const speed = label.replace('Speed Limit ', '')
    html = `
      <div style="width: 32px; height: 32px; background: #ffffff; border: 3px solid #ef4444; border-radius: 50%; color: #000000; font-family: 'Outfit', Arial, sans-serif; font-size: 13px; font-weight: 800; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 4px rgba(0,0,0,0.35); box-sizing: border-box;">
        ${speed}
      </div>
    `
  } else if (label === 'No Parking') {
    html = `
      <div style="width: 32px; height: 32px; background: #2563eb; border: 3px solid #ef4444; border-radius: 50%; color: #ffffff; font-family: 'Outfit', Arial, sans-serif; font-size: 16px; font-weight: 900; display: flex; align-items: center; justify-content: center; position: relative; box-shadow: 0 2px 4px rgba(0,0,0,0.35); box-sizing: border-box;">
        P
        <div style="position: absolute; width: 28px; height: 3px; background: #ef4444; transform: rotate(45deg); top: 12.5px; left: -1px;"></div>
      </div>
    `
  } else if (label === 'No Stopping') {
    html = `
      <div style="width: 32px; height: 32px; background: #2563eb; border: 3px solid #ef4444; border-radius: 50%; position: relative; box-shadow: 0 2px 4px rgba(0,0,0,0.35); box-sizing: border-box;">
        <div style="position: absolute; width: 28px; height: 3px; background: #ef4444; transform: rotate(45deg); top: 12.5px; left: -1px;"></div>
        <div style="position: absolute; width: 28px; height: 3px; background: #ef4444; transform: rotate(-45deg); top: 12.5px; left: -1px;"></div>
      </div>
    `
  } else if (label === 'Stop Sign') {
    html = `
      <div style="width: 32px; height: 32px; background: #ef4444; clip-path: polygon(30% 0%, 70% 0%, 100% 30%, 100% 70%, 70% 100%, 30% 100%, 0% 70%, 0% 30%); color: #ffffff; font-family: 'Outfit', Arial, sans-serif; font-size: 9px; font-weight: 900; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 4px rgba(0,0,0,0.35); box-sizing: border-box;">
        STOP
      </div>
    `
  } else if (label === 'Speed Bump') {
    html = `
      <div style="position: relative; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center;">
        <svg width="36" height="36" viewBox="0 0 36 36" style="position: absolute; top:0; left:0; filter: drop-shadow(0px 2px 4px rgba(0,0,0,0.35));">
          <polygon points="18,3 33,31 3,31" fill="#ffffff" stroke="#ef4444" stroke-width="3" stroke-linejoin="round"/>
          <path d="M 8,26 C 11,26 12,26 13,25 C 15,22 16,18 18,18 C 20,18 21,22 23,25 C 24,26 25,26 28,26 L 28,29 L 8,29 Z" fill="#111827" />
        </svg>
      </div>
    `
  } else if (label === 'Pedestrian Crossing') {
    html = `
      <div style="position: relative; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center;">
        <svg width="36" height="36" viewBox="0 0 36 36" style="position: absolute; top:0; left:0; filter: drop-shadow(0px 2px 4px rgba(0,0,0,0.35));">
          <polygon points="18,3 33,31 3,31" fill="#ffffff" stroke="#ef4444" stroke-width="3" stroke-linejoin="round"/>
          <path d="M 9,29 L 13,29 L 9,22 L 5,22 Z M 14,29 L 18,29 L 14,22 L 10,22 Z M 19,29 L 23,29 L 19,22 L 15,22 Z M 24,29 L 28,29 L 24,22 L 20,22 Z M 29,29 L 33,29 L 29,22 L 25,22 Z" fill="#111827" />
          <circle cx="18" cy="13" r="2.5" fill="#111827" />
          <path d="M 18,15.5 C 16.5,15.5 15.5,16.5 15,17.5 L 13.5,20 C 13,21 13.5,21.5 14,21 L 16,19.5 L 15.5,25 L 15,29 L 16.5,29 L 17.5,25 L 18.5,29 L 20,29 L 19,24 L 19.5,20 L 21,21 C 21.5,21.5 22,21 21.5,20 C 21,19 20,17 19.5,16 C 19,15.5 18.5,15.5 18,15.5 Z" fill="#111827" />
        </svg>
      </div>
    `
  } else if (label === 'Curve Left') {
    html = `
      <div style="position: relative; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center;">
        <svg width="36" height="36" viewBox="0 0 36 36" style="position: absolute; top:0; left:0; filter: drop-shadow(0px 2px 4px rgba(0,0,0,0.35));">
          <polygon points="18,3 33,31 3,31" fill="#ffffff" stroke="#ef4444" stroke-width="3" stroke-linejoin="round"/>
          <path d="M 21,26 L 21,20 C 21,17 17,17 14,17" fill="none" stroke="#111827" stroke-width="3.5" stroke-linecap="round"/>
          <path d="M 17,13.5 L 13,17 L 17,20.5" fill="none" stroke="#111827" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
    `
  } else if (label === 'Curve Right') {
    html = `
      <div style="position: relative; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center;">
        <svg width="36" height="36" viewBox="0 0 36 36" style="position: absolute; top:0; left:0; filter: drop-shadow(0px 2px 4px rgba(0,0,0,0.35));">
          <polygon points="18,3 33,31 3,31" fill="#ffffff" stroke="#ef4444" stroke-width="3" stroke-linejoin="round"/>
          <path d="M 15,26 L 15,20 C 15,17 19,17 22,17" fill="none" stroke="#111827" stroke-width="3.5" stroke-linecap="round"/>
          <path d="M 19,13.5 L 23,17 L 19,20.5" fill="none" stroke="#111827" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
    `
  } else if (label === 'School Zone') {
    html = `
      <div style="position: relative; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center;">
        <svg width="36" height="36" viewBox="0 0 36 36" style="position: absolute; top:0; left:0; filter: drop-shadow(0px 2px 4px rgba(0,0,0,0.35));">
          <polygon points="18,2 34,18 18,34 2,18" fill="#fec006" stroke="#000000" stroke-width="1.5" stroke-linejoin="round"/>
          <polygon points="18,4 32,18 18,32 4,18" fill="none" stroke="#000000" stroke-width="1"/>
          <text x="18" y="12.5" font-family="Arial, sans-serif" font-size="4.2px" font-weight="900" text-anchor="middle" fill="#000000">SLOW</text>
          <text x="18" y="19" font-family="Arial, sans-serif" font-size="4.2px" font-weight="900" text-anchor="middle" fill="#000000">SCHOOL</text>
          <text x="18" y="25.5" font-family="Arial, sans-serif" font-size="4.2px" font-weight="900" text-anchor="middle" fill="#000000">ZONE</text>
        </svg>
      </div>
    `
  } else if (label === 'Roadworks') {
    html = `
      <div style="position: relative; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center;">
        <svg width="36" height="36" viewBox="0 0 36 36" style="position: absolute; top:0; left:0; filter: drop-shadow(0px 2px 4px rgba(0,0,0,0.35));">
          <polygon points="18,3 33,31 3,31" fill="#fec006" stroke="#ef4444" stroke-width="3" stroke-linejoin="round"/>
          <circle cx="19.5" cy="11.5" r="2" fill="#111827" />
          <path d="M 21,30 L 29,30 C 27,24 22,24 21,30 Z" fill="#111827" />
          <line x1="12" y1="18" x2="23" y2="24" stroke="#111827" stroke-width="1.8" stroke-linecap="round"/>
          <path d="M 17,14 C 15.5,14 14.5,15 14,16.5 L 12.5,20 C 12.2,20.5 12.5,21 13,21 L 14,19.5 L 14,23 L 11,27.5 L 12.5,28.5 L 15,24 L 16.5,29 L 18,29 L 18,22 L 18.5,19 L 20,22 C 20.5,23 21,22.5 20.5,21.5 L 19,17.5 L 18.5,15.5 C 18,14.5 17.5,14 17,14 Z" fill="#111827" />
        </svg>
      </div>
    `
  } else if (label === 'Traffic Signals') {
    html = `
      <div style="position: relative; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center;">
        <svg width="36" height="36" viewBox="0 0 36 36" style="position: absolute; top:0; left:0; filter: drop-shadow(0px 2px 4px rgba(0,0,0,0.35));">
          <polygon points="18,3 33,31 3,31" fill="#ffffff" stroke="#ef4444" stroke-width="3" stroke-linejoin="round"/>
          <rect x="15.5" y="10" width="5" height="15" rx="1.5" fill="#374151"/>
          <circle cx="18" cy="12.5" r="1.5" fill="#ef4444"/>
          <circle cx="18" cy="17.5" r="1.5" fill="#fec006"/>
          <circle cx="18" cy="22.5" r="1.5" fill="#10b981"/>
        </svg>
      </div>
    `
  } else if (label === 'Turn Left') {
    html = `
      <div style="width: 32px; height: 32px; background: #ffffff; border: 3px solid #ef4444; border-radius: 50%; display: flex; align-items: center; justify-content: center; position: relative; box-shadow: 0 2px 4px rgba(0,0,0,0.35); box-sizing: border-box;">
        <svg width="32" height="32" viewBox="0 0 32 32" style="position: absolute; top:0; left:0;">
          <path d="M 18,25 L 18,17 C 18,15 17,14 15,14 L 11,14" fill="none" stroke="#111827" stroke-width="4.5" stroke-linecap="square"/>
          <path d="M 14,9.5 L 9,14 L 14,18.5" fill="none" stroke="#111827" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
    `
  } else if (label === 'Turn Right') {
    html = `
      <div style="width: 32px; height: 32px; background: #ffffff; border: 3px solid #ef4444; border-radius: 50%; display: flex; align-items: center; justify-content: center; position: relative; box-shadow: 0 2px 4px rgba(0,0,0,0.35); box-sizing: border-box;">
        <svg width="32" height="32" viewBox="0 0 32 32" style="position: absolute; top:0; left:0;">
          <path d="M 14,25 L 14,17 C 14,15 15,14 17,14 L 21,14" fill="none" stroke="#111827" stroke-width="4.5" stroke-linecap="square"/>
          <path d="M 18,9.5 L 23,14 L 18,18.5" fill="none" stroke="#111827" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
    `
  } else if (cat === 'warning') {
    let emoji = '⚠️'
    if (label.includes('Pedestrian')) emoji = '🚶'
    else if (label.includes('School') || label.includes('Children')) emoji = '🧒'
    else if (label.includes('Curve Left') || label.includes('Chevron Left')) emoji = '↩️'
    else if (label.includes('Curve Right') || label.includes('Chevron Right')) emoji = '↪️'
    else if (label.includes('Uneven Road')) emoji = '〰️'
    else if (label.includes('Junction')) emoji = '🚸'
    
    html = `
      <div style="position: relative; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center;">
        <svg width="36" height="36" viewBox="0 0 36 36" style="position: absolute; top:0; left:0; filter: drop-shadow(0px 2px 4px rgba(0,0,0,0.35));">
          <polygon points="18,3 33,31 3,31" fill="#ffffff" stroke="#ef4444" stroke-width="3" stroke-linejoin="round"/>
        </svg>
        <span style="font-size: 13px; margin-top: 7px; z-index: 1;">${emoji}</span>
      </div>
    `
  } else if (cat === 'regulatory') {
    let emoji = '🚫'
    if (label.includes('No Left Turn')) emoji = '↩️'
    else if (label.includes('No Right Turn')) emoji = '↪️'
    else if (label.includes('No Entry')) emoji = '⛔'
    else if (label.includes('One Way')) emoji = '⬆️'
    
    html = `
      <div style="width: 32px; height: 32px; background: #ffffff; border: 3px solid #ef4444; border-radius: 50%; color: #ef4444; font-size: 15px; display: flex; align-items: center; justify-content: center; position: relative; box-shadow: 0 2px 4px rgba(0,0,0,0.35); box-sizing: border-box;">
        <span style="font-size: 13px; z-index: 1;">${emoji}</span>
        <div style="position: absolute; width: 28px; height: 3px; background: #ef4444; transform: rotate(45deg); top: 12.5px; left: -1px;"></div>
      </div>
    `
  } else {
    let emoji = 'ℹ️'
    if (label === 'Parking') {
      html = `
        <div style="width: 30px; height: 30px; background: #2563eb; border: 2px solid #ffffff; border-radius: 4px; color: #ffffff; font-family: 'Outfit', Arial, sans-serif; font-size: 16px; font-weight: 800; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 4px rgba(0,0,0,0.35); box-sizing: border-box;">
          P
        </div>
      `
      return L.divIcon({
        html,
        className: '',
        iconSize: [30, 30],
        iconAnchor: [15, 15]
      })
    }
    if (label.includes('Disabled')) emoji = '♿'
    else if (label.includes('Highway') || label.includes('Interchange')) emoji = '🛣️'
    
    html = `
      <div style="width: 30px; height: 30px; background: #2563eb; border: 2px solid #ffffff; border-radius: 4px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 4px rgba(0,0,0,0.35); box-sizing: border-box;">
        <span style="font-size: 14px;">${emoji}</span>
      </div>
    `
    return L.divIcon({
      html,
      className: '',
      iconSize: [30, 30],
      iconAnchor: [15, 15]
    })
  }

  return L.divIcon({
    html,
    className: '',
    iconSize: [36, 36],
    iconAnchor: [18, 18]
  })
}

function MapListener({
  onBoundsChange,
  onZoomChange,
}: {
  onBoundsChange: (bounds: any) => void
  onZoomChange: (zoom: number) => void
}) {
  const map = useMapEvents({
    moveend() {
      onBoundsChange(map.getBounds())
      onZoomChange(map.getZoom())
    },
    zoomend() {
      onBoundsChange(map.getBounds())
      onZoomChange(map.getZoom())
    },
  })

  useEffect(() => {
    onBoundsChange(map.getBounds())
    onZoomChange(map.getZoom())
  }, [map])

  return null
}

// Leaflet recentering component helper
function ChangeView({ center, resetTrigger }: { center: [number, number], resetTrigger: number }) {
  const map = useMap()
  useEffect(() => {
    map.setView(center, 15)
  }, [center, resetTrigger, map])
  return null
}

export function LiveMapPage() {
  const shellRef = useRef<HTMLDivElement>(null)
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

  // Mapillary Traffic Signs
  const [allTrafficSigns, setAllTrafficSigns] = useState<any[]>([])
  const [currentBounds, setCurrentBounds] = useState<any>(null)
  const [zoomLevel, setZoomLevel] = useState<number>(15)
  const [isMapFullScreen, setIsMapFullScreen] = useState(false)
  const [currentAlert, setCurrentAlert] = useState<string | null>(null)
  const [demoRunning, setDemoRunning] = useState(false)
  const [resetTrigger, setResetTrigger] = useState(0)

  const triggerScreenAlert = (message: string) => {
    setCurrentAlert(message)
    setTimeout(() => {
      setCurrentAlert(prev => prev === message ? null : prev)
    }, 4500)
  }

  useEffect(() => {
    const handleFsChange = () => {
      setIsMapFullScreen(!!document.fullscreenElement)
    }
    document.addEventListener('fullscreenchange', handleFsChange)
    return () => {
      document.removeEventListener('fullscreenchange', handleFsChange)
    }
  }, [])

  // Automated V2I2V demonstration loop
  useEffect(() => {
    if (!demoRunning) return
    
    let step = 0
    const runDemoStep = async () => {
      if (step === 0) {
        triggerScreenAlert("🚀 Auto Demo: Vehicle OBU-01 started trip near Kengeri.")
        setSimCoords({ lat: '12.924285', lng: '77.499673' })
        setMapCenter([12.924285, 77.499673])
      } else if (step === 1) {
        triggerScreenAlert("🌫️ Auto Demo: Camera extracts fog features; XGBoost computes 68% risk.")
        try {
          await fetch(withBase('/api/simulate/fog/'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lat: 12.924285, lng: 77.499673, fog_level: 'HIGH', risk_score: 0.68, source_id: 'OBU-01' })
          })
          fetchAllData()
        } catch (e) {
          console.error(e)
        }
      } else if (step === 2) {
        triggerScreenAlert("⚠️ Auto Demo: YOLOv8 detects CRITICAL pothole! Transmitting warn signal...")
        try {
          await fetch(withBase('/api/simulate/pothole/'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lat: 12.924285, lng: 77.499673, severity: 'CRITICAL', source_id: 'OBU-01' })
          })
          fetchAllData()
        } catch (e) {
          console.error(e)
        }
      } else if (step === 3) {
        triggerScreenAlert("📡 Auto Demo: RSU-01 gateway captures broadcast, relaying to infrastructure...")
        try {
          await fetch(withBase('/api/telemetry/ingest/'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              source_id: 'RSU_RSU_Pothole_12.924285_77.499673',
              lat: 12.924285,
              lng: 77.499673,
              speed_kmph: 35.0,
              event: 'RSU_Pothole',
              status: 'DISSEMINATED',
              device_ts: Math.floor(Date.now() / 1000),
              seq: 1
            })
          })
          fetchAllData()
        } catch (e) {
          console.error(e)
        }
      } else if (step === 4) {
        triggerScreenAlert("🚗 Auto Demo: Vehicle OBU-02 receives warning over ESP-NOW (V2I2V).")
        try {
          await fetch(withBase('/api/telemetry/ingest/'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              source_id: 'OBU2_OBU_Pothole_12.924285_77.499673',
              lat: 12.924285,
              lng: 77.499673,
              speed_kmph: 30.0,
              event: 'OBU_Pothole',
              status: 'RECEIVED',
              device_ts: Math.floor(Date.now() / 1000),
              seq: 1
            })
          })
          fetchAllData()
        } catch (e) {
          console.error(e)
        }
      } else {
        triggerScreenAlert("🏁 Auto Demo Finished! Resetting alerts...")
        setDemoRunning(false)
        return
      }
      step++
    }

    runDemoStep()
    const interval = setInterval(runDemoStep, 4500)
    
    return () => clearInterval(interval)
  }, [demoRunning])

  useEffect(() => {
    const loadSigns = async () => {
      try {
        const res = await fetch('/mapillary_traffic_signs.json')
        if (res.ok) {
          const data = await res.json()
          setAllTrafficSigns(data)
        }
      } catch (err) {
        console.error('Failed to load Mapillary traffic signs:', err)
      }
    }
    loadSigns()
  }, [])

  const isInside = (lat: number, lng: number) => {
    if (!currentBounds) return false
    const ne = currentBounds.getNorthEast()
    const sw = currentBounds.getSouthWest()
    return lat >= sw.lat && lat <= ne.lat && lng >= sw.lng && lng <= ne.lng
  }

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
        triggerScreenAlert(`⚠️ Manual Pothole Ingest: ${simSeverity} Alert triggered at ${lat.toFixed(6)}, ${lng.toFixed(6)}`)
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
        triggerScreenAlert(`🌫️ Manual Fog Ingest: ${simFogLevel} Alert triggered at ${lat.toFixed(6)}, ${lng.toFixed(6)}`)
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
              <div ref={shellRef} className="leaflet-shell" style={
                isMapFullScreen ? {
                  position: 'fixed',
                  top: 0,
                  left: 0,
                  width: '100vw',
                  height: '100vh',
                  zIndex: 9999,
                  background: '#000000'
                } : {
                  position: 'relative',
                  height: '100%'
                }
              }>
                {/* Fullscreen Button */}
                <button
                  onClick={() => {
                    const el = shellRef.current
                    if (!el) return
                    if (!document.fullscreenElement) {
                      el.requestFullscreen().catch(err => {
                        console.error('Error entering fullscreen:', err)
                      })
                    } else {
                      document.exitFullscreen()
                    }
                  }}
                  style={{
                    position: 'absolute',
                    top: '10px',
                    right: '10px',
                    zIndex: 1000,
                    background: 'rgba(15, 23, 42, 0.9)',
                    color: '#ffffff',
                    border: '1px solid rgba(255, 255, 255, 0.2)',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    fontSize: '0.8em',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
                    transition: 'all 0.2s',
                    fontFamily: "'Outfit', Arial, sans-serif"
                  }}
                >
                  {isMapFullScreen ? 'Exit Fullscreen' : 'Fullscreen'}
                </button>

                {/* Screen alerts overlay HUD */}
                {currentAlert && (
                  <div className="hud-alert-overlay" style={{
                    position: 'absolute',
                    top: '20px',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    background: 'rgba(15, 23, 42, 0.95)',
                    color: '#ffffff',
                    padding: '12px 24px',
                    borderRadius: '8px',
                    zIndex: 10001,
                    fontSize: '0.9em',
                    fontWeight: 'bold',
                    border: '1.5px solid #ef4444',
                    boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
                    textAlign: 'center',
                    minWidth: '320px',
                    pointerEvents: 'none',
                    fontFamily: "'Outfit', Arial, sans-serif"
                  }}>
                    {currentAlert}
                  </div>
                )}

                <MapContainer center={mapCenter} zoom={15} scrollWheelZoom style={{ height: '100%', width: '100%' }}>
                  <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />
                  <ChangeView center={mapCenter} resetTrigger={resetTrigger} />

                  {/* 1. Dynamic Mapillary Road signs and humps overlays */}
                  <MapListener onBoundsChange={setCurrentBounds} onZoomChange={setZoomLevel} />

                  {activeLayers.humps && zoomLevel >= 15 && allTrafficSigns
                    .filter(s => s.label === 'Speed Bump' && isInside(s.lat, s.lng))
                    .slice(0, 150)
                    .map(s => (
                      <Marker
                        key={`hump-${s.id}`}
                        position={[s.lat, s.lng]}
                        icon={createSignIcon('Speed Bump', 'warning')}
                      >
                        <Popup>
                          <div style={{ color: '#000' }}>
                            <strong style={{ color: '#ea580c' }}>🚧 Road Hump (Mapillary)</strong><br />
                            <strong>Type:</strong> Speed Bump / Hump<br />
                            <strong>GPS:</strong> {s.lat.toFixed(6)}, {s.lng.toFixed(6)}
                          </div>
                        </Popup>
                      </Marker>
                    ))
                  }

                  {activeLayers.signs && zoomLevel >= 15 && allTrafficSigns
                    .filter(s => s.label !== 'Speed Bump' && isInside(s.lat, s.lng))
                    .slice(0, 150)
                    .map(s => {
                      let markerColor = '#3b82f6'
                      if (s.cat === 'warning') {
                        markerColor = '#f59e0b'
                      } else if (s.cat === 'regulatory') {
                        markerColor = '#ef4444'
                      } else if (s.cat === 'information') {
                        markerColor = '#3b82f6'
                      } else {
                        markerColor = '#6b7280'
                      }
                      
                      return (
                        <Marker
                          key={`sign-${s.id}`}
                          position={[s.lat, s.lng]}
                          icon={createSignIcon(s.label, s.cat)}
                        >
                          <Popup>
                            <div style={{ color: '#000' }}>
                              <strong style={{ color: markerColor }}>🚦 Traffic Sign (Mapillary)</strong><br />
                              <strong>Name:</strong> {s.label}<br />
                              <strong>Category:</strong> {s.cat.toUpperCase()}<br />
                              <strong>GPS:</strong> {s.lat.toFixed(6)}, {s.lng.toFixed(6)}
                            </div>
                          </Popup>
                        </Marker>
                      )
                    })
                  }

                  {/* Specific Composite Risk Heatmaps around actual threats */}
                  {activeLayers.risk && potholesList.map((item) => {
                    const lat = item.coordinates?.lat
                    const lng = item.coordinates?.lng
                    if (!lat || !lng) return null
                    return (
                      <Circle
                        key={`risk-pot-${item.id}`}
                        center={[lat, lng]}
                        radius={60}
                        pathOptions={{ color: '#a855f7', fillColor: '#a855f7', fillOpacity: 0.12, weight: 1.5 }}
                      >
                        <Popup>Composite Risk Alert (Pothole Hazard Zone)</Popup>
                      </Circle>
                    )
                  })}

                  {activeLayers.risk && fogList.map((item) => {
                    const lat = item.coordinates?.lat
                    const lng = item.coordinates?.lng
                    if (!lat || !lng) return null
                    return (
                      <Circle
                        key={`risk-fog-${item.request_id || item.updated_at}`}
                        center={[lat, lng]}
                        radius={120}
                        pathOptions={{ color: '#a855f7', fillColor: '#a855f7', fillOpacity: 0.08, weight: 1.5 }}
                      >
                        <Popup>Composite Risk Alert (Fog Hazard Sector)</Popup>
                      </Circle>
                    )
                  })}

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

                  {/* 4. Dynamic ESP32 Telemetry / RSU & OBU warnings received via ESP-NOW */}
                  {activeLayers.rsu && telemetryList.map((item) => {
                    const lat = item.lat
                    const lng = item.lng
                    if (!lat || !lng) return null

                    const isObu = item.event?.startsWith('OBU_')
                    const isPothole = item.event === 'RSU_Pothole' || item.event === 'OBU_Pothole'
                    
                    let markerColor = '#8b5cf6'
                    let markerFill = '#c084fc'
                    let title = '📡 RSU Recv Warning (ESP-NOW)'
                    let sourceNode = 'OBU-01'
                    
                    if (isObu) {
                      markerColor = isPothole ? '#d97706' : '#ea580c' // Amber for pothole, Orange for fog
                      markerFill = isPothole ? '#f59e0b' : '#f97316'
                      title = '🚗 Vehicle OBU-02 Recv Alert (V2I2V)'
                      sourceNode = 'RSU-01 (via ESP-NOW)'
                    } else {
                      markerColor = isPothole ? '#8b5cf6' : '#2563eb' // Purple for pothole, Blue for fog
                      markerFill = isPothole ? '#c084fc' : '#60a5fa'
                      title = '📡 RSU Recv Warning (ESP-NOW)'
                      sourceNode = 'OBU-01'
                    }
                    
                    return (
                      <CircleMarker
                        key={`tel-${item.source_id || item.updated_at}`}
                        center={[lat, lng]}
                        radius={13}
                        pathOptions={{ color: markerColor, fillColor: markerFill, fillOpacity: 0.8, weight: 3, dashArray: '2, 2' }}
                      >
                        <Popup>
                          <div style={{ color: '#000' }}>
                            <strong style={{ color: markerColor }}>{title}</strong><br />
                            <strong>Hazard:</strong> {isPothole ? 'POTHOLE' : 'FOG'}<br />
                            <strong>Source Node:</strong> {sourceNode}<br />
                            <strong>Status:</strong> {item.status || 'DISSEMINATED'}<br />
                            <strong>Node Speed:</strong> {item.speed_kmph} km/h<br />
                            <strong>Received At:</strong> {new Date(item.updated_at * 1000).toLocaleTimeString()}
                          </div>
                        </Popup>
                      </CircleMarker>
                    )
                  })}
                </MapContainer>
                
                {/* Zoom warning overlay */}
                {zoomLevel < 15 && (activeLayers.signs || activeLayers.humps) && (
                  <div className="map-zoom-warning" style={{
                    position: 'absolute',
                    top: '10px',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    background: 'rgba(0,0,0,0.85)',
                    color: '#fbbf24',
                    padding: '8px 16px',
                    borderRadius: '20px',
                    zIndex: 1000,
                    fontSize: '0.85em',
                    fontWeight: 'bold',
                    border: '1px solid #fbbf24',
                    pointerEvents: 'none'
                  }}>
                    🔍 Zoom in to view Mapillary Traffic Signs & Humps
                  </div>
                )}
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

          {/* OBU V2X (V2I2V) Simulator panel */}
          <BorderGlow className="panel glass">
            <ShinyText text="OBU V2X (V2I2V) Simulator" className="text-xl font-bold mb-3" color="#ffffff" shineColor="#ffffff" />
            
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

              <div style={{ display: 'flex', gap: '8px', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '10px' }}>
                <button
                  type="button"
                  onClick={() => {
                    setMapCenter([12.9242853, 77.4996733])
                    setSimCoords({ lat: '12.9242853', lng: '77.4996733' })
                    setTriggerStatus('')
                    setCurrentAlert(null)
                    setResetTrigger(prev => prev + 1)
                  }}
                  style={{ flex: 1, background: 'transparent', color: '#6b7280', border: '1px solid rgba(255,255,255,0.15)', padding: '10px', borderRadius: '8px', cursor: 'pointer', fontSize: '0.85em', fontWeight: 'bold' }}
                >
                  Reset View
                </button>
                <button
                  type="button"
                  onClick={() => setDemoRunning(prev => !prev)}
                  style={{
                    flex: 1,
                    background: demoRunning ? '#ef4444' : '#10b981',
                    color: '#ffffff',
                    border: 'none',
                    padding: '10px',
                    borderRadius: '8px',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    fontSize: '0.85em',
                    boxShadow: demoRunning ? '0 4px 8px rgba(239,68,68,0.2)' : '0 4px 8px rgba(16,185,129,0.2)'
                  }}
                >
                  {demoRunning ? 'Stop Demo' : 'Auto Demo'}
                </button>
              </div>

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
