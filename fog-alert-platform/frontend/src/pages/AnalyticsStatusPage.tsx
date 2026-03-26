import GradientText from '@/components/GradientText'

export function AnalyticsStatusPage() {
  return (
    <div className="page">
      <GradientText className="page-title text-4xl font-bold" colors={['#5227FF', '#FF9FFC', '#B19EEF']} animationSpeed={6}>
        Analytics + System Status
      </GradientText>

      <section className="grid dashboard-main">
        <article className="panel glass">
          <GradientText className="text-xl font-bold mb-3" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
            Analytics
          </GradientText>
          <div className="fake-chart compact">
            <div className="line wave-1" />
          </div>
          <p className="text-white">Fog occurrence graph • Hazard distribution • Risk trends</p>

          <div className="insight-block">
            <GradientText className="text-lg font-bold mb-2" colors={['#4b84ff', '#9b59ff']} animationSpeed={10}>
              Insights
            </GradientText>
            <p>Peak Fog Time: 5–7 AM</p>
            <p>High Risk Zone: NH75 Valley</p>
          </div>
        </article>

        <aside className="panel glass insights-panel">
          <GradientText className="text-xl font-bold mb-3" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
            System Status
          </GradientText>
          <div className="status-row">
            <span>YOLOv8</span>
            <strong className="status-ok">Running</strong>
          </div>
          <div className="status-row">
            <span>XGBoost</span>
            <strong className="status-ok">Running</strong>
          </div>
          <div className="status-row">
            <span>FPS</span>
            <strong>18</strong>
          </div>
          <div className="status-row">
            <span>Latency</span>
            <strong>210 ms</strong>
          </div>
          <div className="status-row">
            <span>API Health</span>
            <strong className="status-ok">Healthy</strong>
          </div>
          <div className="status-row">
            <span>Data Stream</span>
            <strong className="status-ok">Active</strong>
          </div>
        </aside>
      </section>
    </div>
  )
}
