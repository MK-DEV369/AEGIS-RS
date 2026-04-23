import { useState } from 'react'
import { Circle, CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'
import BorderGlow from '@/components/BorderGlow'
import ShinyText from '@/components/ShinyText'

type LayerKey = 'fog' | 'potholes' | 'signs' | 'humps' | 'risk'

const layerLabels: Record<LayerKey, string> = {
  fog: 'Fog',
  potholes: 'Potholes',
  signs: 'Traffic Signs',
  humps: 'Road Humps',
  risk: 'Risk Heatmap',
}

const initialLayers: Record<LayerKey, boolean> = {
  fog: true,
  potholes: true,
  signs: true,
  humps: true,
  risk: true,
}

const mapCenter: [number, number] = [12.9716, 77.5946]

export function LiveMapPage() {
  const [activeLayers, setActiveLayers] = useState<Record<LayerKey, boolean>>(initialLayers)

  const toggleLayer = (layer: LayerKey) => {
    setActiveLayers((prev) => ({ ...prev, [layer]: !prev[layer] }))
  }

  return (
    <div className="page">
      <section>
        <BorderGlow className="panel glass">
          <div className="alert-toolbar">
            <ShinyText text="Map Layers" className="text-xl font-bold" color="#ffffff" shineColor="#ffffff" />
          </div>

          <div className="stack-grid">
            {(Object.keys(layerLabels) as LayerKey[]).map((layerKey) => (
              <label key={layerKey} className="chip checkbox-chip">
                <input
                  type="checkbox"
                  checked={activeLayers[layerKey]}
                  onChange={() => toggleLayer(layerKey)}
                />
                {layerLabels[layerKey]}
              </label>
            ))}
          </div>

          <div className="map-canvas live-map fullscreen">
            <div className="leaflet-shell">
              <MapContainer center={mapCenter} zoom={13} scrollWheelZoom style={{ height: '100%', width: '100%' }}>
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                {activeLayers.fog && (
                  <Circle center={[12.9697, 77.5972]} radius={350} pathOptions={{ color: '#22c55e', fillOpacity: 0.2 }}>
                    <Popup>Fog Cluster: Moderate Visibility Drop</Popup>
                  </Circle>
                )}

                {activeLayers.potholes && (
                  <>
                    <CircleMarker center={[12.9741, 77.589]} radius={8} pathOptions={{ color: '#ef4444' }}>
                      <Popup>Pothole Zone A</Popup>
                    </CircleMarker>
                    <CircleMarker center={[12.9684, 77.601]} radius={8} pathOptions={{ color: '#ef4444' }}>
                      <Popup>Pothole Zone B</Popup>
                    </CircleMarker>
                  </>
                )}

                {activeLayers.signs && (
                  <CircleMarker center={[12.977, 77.5968]} radius={7} pathOptions={{ color: '#3b82f6' }}>
                    <Popup>Traffic Sign Region</Popup>
                  </CircleMarker>
                )}

                {activeLayers.humps && (
                  <CircleMarker center={[12.9669, 77.5925]} radius={7} pathOptions={{ color: '#f59e0b' }}>
                    <Popup>Road Hump Section</Popup>
                  </CircleMarker>
                )}

                {activeLayers.risk && (
                  <Circle center={[12.9716, 77.5946]} radius={800} pathOptions={{ color: '#a855f7', fillOpacity: 0.14 }}>
                    <Popup>Composite Risk Heat Zone</Popup>
                  </Circle>
                )}
              </MapContainer>
            </div>
          </div>
        </BorderGlow>
      </section>
    </div>
  )
}
