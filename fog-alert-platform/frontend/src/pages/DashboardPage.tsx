import GradientText from '@/components/GradientText'

const kpis = [
  { label: 'Risk Score', value: '72 / 100' },
  { label: 'Fog Level', value: 'Moderate' },
  { label: 'Visibility', value: '80 m' },
  { label: 'Active Alerts', value: '5' },
]

export function DashboardPage() {
  return (
    <div className="page">
      <GradientText className="page-title text-4xl font-bold" colors={['#5227FF', '#FF9FFC', '#B19EEF']} animationSpeed={6}>
        Main Dashboard
      </GradientText>

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
          <GradientText className="text-xl font-bold mb-3" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
            Interactive Map
          </GradientText>
          <div className="map-canvas">
            <span className="marker marker-red">Hazard</span>
            <span className="marker marker-yellow">Fog Zone</span>
            <span className="marker marker-blue">Risk Heatmap</span>
          </div>
        </article>

        <aside className="panel glass insights-panel">
          <GradientText className="text-xl font-bold mb-3" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
            AI Insights Panel
          </GradientText>
          <div className="insight-block">
            <GradientText className="text-lg font-bold mb-2" colors={['#4b84ff', '#9b59ff']} animationSpeed={10}>
              AI Risk Breakdown
            </GradientText>
            <p>Fog: 45%</p>
            <p>Traffic: 30%</p>
            <p>Potholes: 25%</p>
          </div>
          <div className="insight-block">
            <GradientText className="text-lg font-bold mb-2" colors={['#4b84ff', '#9b59ff']} animationSpeed={10}>
              Model Outputs
            </GradientText>
            <p>Fog Probability: 0.78</p>
            <p>Detected Objects: Pothole, Sign</p>
            <p>Confidence: 0.92, 0.84</p>
          </div>
        </aside>
      </section>

      <section className="grid two-col">
        <article className="panel glass chart-card">
          <GradientText className="text-xl font-bold mb-3" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
            Risk Over Time
          </GradientText>
          <div className="fake-chart">
            <div className="line wave-1" />
          </div>
        </article>

        <article className="panel glass chart-card">
          <GradientText className="text-xl font-bold mb-3" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
            Fog Prediction Trend
          </GradientText>
          <div className="fake-chart">
            <div className="line wave-2" />
          </div>
        </article>
      </section>
    </div>
  )
}
