import { motion } from 'framer-motion'
import { Circle, CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'
import BorderGlow from '@/components/BorderGlow'
import ShinyText from '@/components/ShinyText'

const kpis = [
  { label: 'Risk Score', value: '72 / 100' },
  { label: 'Fog Level', value: 'Moderate' },
  { label: 'Visibility', value: '80 m' },
  { label: 'Active Alerts', value: '5' },
]

const mapCenter: [number, number] = [12.9716, 77.5946]

export function DashboardPage() {
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
              <p>Fog: 45%</p>
              <p>Traffic: 30%</p>
              <p>Potholes: 25%</p>
            </div>
            <div className="insight-block">
              <ShinyText text="Model Outputs" className="text-lg font-bold mb-2" color="#ffffff" shineColor="#ffffff" />
              <p>Fog Probability: 0.78</p>
              <p>Detected Objects: Pothole, Sign</p>
              <p>Confidence: 0.92, 0.84</p>
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
            <div className="fake-chart">
              <div className="line wave-1" />
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
            <div className="fake-chart">
              <div className="line wave-2" />
            </div>
          </BorderGlow>
        </motion.article>
      </section>
    </div>
  )
}
