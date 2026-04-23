import BorderGlow from '@/components/BorderGlow'
import ShinyText from '@/components/ShinyText'

export function LiveMonitoringPage() {
  return (
    <div className="page">
      <section className="grid dashboard-main">
        <article className="video-panel">
          <BorderGlow className="panel glass">
            <ShinyText text="Live Video Stream" className="text-xl font-bold mb-3" color="#ffffff" shineColor="#ffffff" />
            <div className="video-placeholder pulse-border">Camera Stream Placeholder</div>
          </BorderGlow>
        </article>

        <aside className="insights-panel">
          <BorderGlow className="panel glass insights-panel">
            <ShinyText text="Detection Panel" className="text-xl font-bold mb-3" color="#ffffff" shineColor="#ffffff" />
            <div className="insight-block">
              <p>Object: Pothole</p>
              <p>Confidence: 92%</p>
              <p>Fog Level: High</p>
            </div>
          </BorderGlow>
        </aside>
      </section>

      <section className="grid two-col">
        <article>
          <BorderGlow className="panel glass">
            <ShinyText text="Before (Foggy)" className="text-xl font-bold mb-3" color="#ffffff" shineColor="#ffffff" />
            <div className="image-box">Foggy Image</div>
          </BorderGlow>
        </article>

        <article>
          <BorderGlow className="panel glass">
            <ShinyText text="After (Enhanced / Dehazed)" className="text-xl font-bold mb-3" color="#ffffff" shineColor="#ffffff" />
            <div className="image-box">Enhanced Image</div>
          </BorderGlow>
        </article>
      </section>
    </div>
  )
}
