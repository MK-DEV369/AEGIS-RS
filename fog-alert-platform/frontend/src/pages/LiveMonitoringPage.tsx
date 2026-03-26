export function LiveMonitoringPage() {
  return (
    <div className="page">
      <h1 className="page-title">Live Monitoring</h1>

      <section className="grid dashboard-main">
        <article className="panel glass video-panel">
          <h3>Live Video Stream</h3>
          <div className="video-placeholder pulse-border">Camera Stream Placeholder</div>
        </article>

        <aside className="panel glass insights-panel">
          <h3>Detection Panel</h3>
          <div className="insight-block">
            <p>Object: Pothole</p>
            <p>Confidence: 92%</p>
            <p>Fog Level: High</p>
          </div>
        </aside>
      </section>

      <section className="grid two-col">
        <article className="panel glass">
          <h3>Before (Foggy)</h3>
          <div className="image-box">Foggy Image</div>
        </article>

        <article className="panel glass">
          <h3>After (Enhanced / Dehazed)</h3>
          <div className="image-box">Enhanced Image</div>
        </article>
      </section>
    </div>
  )
}
