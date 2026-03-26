export function AnalyticsStatusPage() {
  return (
    <div className="page">
      <h1 className="page-title">Analytics + System Status</h1>

      <section className="grid dashboard-main">
        <article className="panel glass">
          <h3>Analytics</h3>
          <div className="fake-chart compact">
            <div className="line wave-1" />
          </div>
          <p>Fog occurrence graph • Hazard distribution • Risk trends</p>

          <div className="insight-block">
            <h4>Insights</h4>
            <p>Peak Fog Time: 5–7 AM</p>
            <p>High Risk Zone: NH75 Valley</p>
          </div>
        </article>

        <aside className="panel glass insights-panel">
          <h3>System Status</h3>
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
