import GradientText from '@/components/GradientText'

export function LiveMonitoringPage() {
  return (
    <div className="page">
      <GradientText className="page-title text-4xl font-bold" colors={['#5227FF', '#FF9FFC', '#B19EEF']} animationSpeed={6}>
        Live Monitoring
      </GradientText>

      <section className="grid dashboard-main">
        <article className="panel glass video-panel">
          <GradientText className="text-xl font-bold mb-3" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
            Live Video Stream
          </GradientText>
          <div className="video-placeholder pulse-border">Camera Stream Placeholder</div>
        </article>

        <aside className="panel glass insights-panel">
          <GradientText className="text-xl font-bold mb-3" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
            Detection Panel
          </GradientText>
          <div className="insight-block">
            <p>Object: Pothole</p>
            <p>Confidence: 92%</p>
            <p>Fog Level: High</p>
          </div>
        </aside>
      </section>

      <section className="grid two-col">
        <article className="panel glass">
          <GradientText className="text-xl font-bold mb-3" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
            Before (Foggy)
          </GradientText>
          <div className="image-box">Foggy Image</div>
        </article>

        <article className="panel glass">
          <GradientText className="text-xl font-bold mb-3" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
            After (Enhanced / Dehazed)
          </GradientText>
          <div className="image-box">Enhanced Image</div>
        </article>
      </section>
    </div>
  )
}
