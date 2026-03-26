import { useState } from 'react'
import GradientText from '@/components/GradientText'

const layers = ['Fog', 'Potholes', 'Traffic Signs', 'Road Humps', 'Risk Heatmap']

export function LiveMapPage() {
  const [fullScreen, setFullScreen] = useState(false)

  return (
    <div className="page">
      <GradientText className="page-title text-4xl font-bold" colors={['#5227FF', '#FF9FFC', '#B19EEF']} animationSpeed={6}>
        Live Map
      </GradientText>

      <section className="panel glass">
        <div className="alert-toolbar">
          <GradientText className="text-xl font-bold" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
            Map Layers
          </GradientText>
          <button className="action-btn" onClick={() => setFullScreen((prev) => !prev)}>
            {fullScreen ? 'Exit Full-Screen' : 'Full-Screen Mode'}
          </button>
        </div>

        <div className="stack-grid">
          {layers.map((layer) => (
            <label key={layer} className="chip checkbox-chip">
              <input type="checkbox" defaultChecked />
              {layer}
            </label>
          ))}
        </div>

        <div className={`map-canvas live-map ${fullScreen ? 'fullscreen' : ''}`}>
          <span className="marker marker-red">Fog Cluster</span>
          <span className="marker marker-yellow">Pothole Zone</span>
          <span className="marker marker-blue">Traffic Sign Region</span>
        </div>
      </section>
    </div>
  )
}
