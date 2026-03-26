import { useState } from 'react'

const layers = ['Fog', 'Potholes', 'Traffic Signs', 'Road Humps', 'Risk Heatmap']

export function LiveMapPage() {
  const [fullScreen, setFullScreen] = useState(false)

  return (
    <div className="page">
      <h1 className="page-title">Live Map</h1>

      <section className="panel glass">
        <div className="alert-toolbar">
          <h3>Map Layers</h3>
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
