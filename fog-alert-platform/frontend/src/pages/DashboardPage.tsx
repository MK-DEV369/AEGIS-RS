const kpis = [
  { label: 'Risk Score', value: '72 / 100' },
  { label: 'Fog Level', value: 'Moderate' },
  { label: 'Visibility', value: '80 m' },
  { label: 'Active Alerts', value: '5' },
]

export function DashboardPage() {
  return (
    <div className="page">
      <h1 className="page-title">Main Dashboard</h1>

      <section className="kpi-grid">
        {kpis.map((kpi) => (
          <article key={kpi.label} className="kpi-card glass">
            <p>{kpi.label}</p>
            <strong>{kpi.value}</strong>
          </article>
        ))}
      </section>

      <section className="grid dashboard-main">
        <article className="panel glass map-panel">
          <h3>Interactive Map</h3>
          <div className="map-canvas">
            <span className="marker marker-red">Hazard</span>
            <span className="marker marker-yellow">Fog Zone</span>
            <span className="marker marker-blue">Risk Heatmap</span>
          </div>
        </article>

        <aside className="panel glass insights-panel">
          <h3>AI Insights Panel</h3>
          <div className="insight-block">
            <h4>AI Risk Breakdown</h4>
            <p>Fog: 45%</p>
            <p>Traffic: 30%</p>
            <p>Potholes: 25%</p>
          </div>
          <div className="insight-block">
            <h4>Model Outputs</h4>
            <p>Fog Probability: 0.78</p>
            <p>Detected Objects: Pothole, Sign</p>
            <p>Confidence: 0.92, 0.84</p>
          </div>
        </aside>
      </section>

      <section className="grid two-col">
        <article className="panel glass chart-card">
          <h3>Risk Over Time</h3>
          <div className="fake-chart">
            <div className="line wave-1" />
          </div>
        </article>

        <article className="panel glass chart-card">
          <h3>Fog Prediction Trend</h3>
          <div className="fake-chart">
            <div className="line wave-2" />
          </div>
        </article>
      </section>
    </div>
  )
}
