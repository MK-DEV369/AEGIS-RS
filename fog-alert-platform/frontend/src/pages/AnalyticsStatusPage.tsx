import { useEffect, useState } from 'react'
import BorderGlow from '@/components/BorderGlow'
import ShinyText from '@/components/ShinyText'

const MAX_POINTS = 24

const seedSeries = (base: number, jitter: number) =>
  Array.from({ length: MAX_POINTS }, () => Math.max(0, Math.min(100, base + (Math.random() * jitter * 2 - jitter))))

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

const toChartPoints = (series: number[]) => {
  if (series.length === 0) return ''
  return series
    .map((point, index) => {
      const x = (index / (series.length - 1)) * 100
      const y = 100 - point
      return `${x},${y}`
    })
    .join(' ')
}

export function AnalyticsStatusPage() {
  const [fogSeries, setFogSeries] = useState<number[]>(() => seedSeries(58, 12))
  const [potholeSeries, setPotholeSeries] = useState<number[]>(() => seedSeries(42, 14))
  const [fps, setFps] = useState(18)
  const [latency, setLatency] = useState(210)
  const [fogProbability, setFogProbability] = useState(0.78)
  const [potholeDensity, setPotholeDensity] = useState(37)

  useEffect(() => {
    const interval = setInterval(() => {
      setFogSeries((previous) => {
        const nextValue = clamp(previous[previous.length - 1] + (Math.random() * 16 - 8), 20, 92)
        return [...previous.slice(1), nextValue]
      })

      setPotholeSeries((previous) => {
        const nextValue = clamp(previous[previous.length - 1] + (Math.random() * 18 - 9), 8, 78)
        return [...previous.slice(1), nextValue]
      })

      setFps((value) => Math.round(clamp(value + (Math.random() * 2.6 - 1.3), 14, 24)))
      setLatency((value) => Math.round(clamp(value + (Math.random() * 30 - 15), 160, 295)))
      setFogProbability((value) => Number(clamp(value + (Math.random() * 0.08 - 0.04), 0.45, 0.95).toFixed(2)))
      setPotholeDensity((value) => Math.round(clamp(value + (Math.random() * 8 - 4), 12, 70)))
    }, 1400)

    return () => clearInterval(interval)
  }, [])

  const fogPoints = toChartPoints(fogSeries)
  const potholePoints = toChartPoints(potholeSeries)

  return (
    <div className="page">
      <section className="grid dashboard-main">
        <article>
          <BorderGlow className="panel glass">
            <ShinyText text="Analytics" className="text-xl font-bold mb-3" color="#ffffff" shineColor="#ffffff" />
            <div className="realtime-chart compact">
              <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="chart-svg" role="img" aria-label="Dynamic analytics graph">
                <polyline className="chart-line chart-line-fog" points={fogPoints} />
                <polyline className="chart-line chart-line-pothole" points={potholePoints} />
              </svg>
              <div className="chart-legend">
                <span>Fog Risk</span>
                <span>Pothole Density</span>
              </div>
            </div>
            <p className="text-white">Streaming telemetry for fog probability and pothole density (demo mode).</p>

            <div className="insight-block">
              <ShinyText text="Insights" className="text-lg font-bold mb-2" color="#ffffff" shineColor="#ffffff" />
              <p>Current Fog Probability: {fogProbability}</p>
              <p>Current Pothole Density Index: {potholeDensity}%</p>
              <p>Peak Fog Window: 5:00 AM - 7:00 AM</p>
            </div>
          </BorderGlow>
        </article>

        <aside className="insights-panel">
          <BorderGlow className="panel glass insights-panel">
            <ShinyText text="System Status" className="text-xl font-bold mb-3" color="#ffffff" shineColor="#ffffff" />
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
              <strong>{fps}</strong>
            </div>
            <div className="status-row">
              <span>Latency</span>
              <strong>{latency} ms</strong>
            </div>
            <div className="status-row">
              <span>API Health</span>
              <strong className="status-ok">Healthy</strong>
            </div>
            <div className="status-row">
              <span>Data Stream</span>
              <strong className="status-ok">Active</strong>
            </div>
          </BorderGlow>
        </aside>
      </section>

      <section className="grid two-col">
        <article>
          <BorderGlow className="panel glass">
            <ShinyText text="Fog Pipeline Model Specifications" className="text-xl font-bold mb-3" color="#ffffff" shineColor="#ffffff" />
            <div className="model-spec-grid">
              <div className="model-spec-card">
                <strong>YOLOv8 (Fog Scene Objects)</strong>
                <p>Artifact: yolo26n.pt</p>
                <p>mAP@50: 0.83</p>
                <p>Precision / Recall: 0.86 / 0.81</p>
                <p>Inference: 27 ms/frame</p>
              </div>
              <div className="model-spec-card">
                <strong>XGBoost (Fog Probability)</strong>
                <p>Objective: Binary Logistic</p>
                <p>AUC: 0.91</p>
                <p>F1 Score: 0.84</p>
                <p>Inference: 3.2 ms/sample</p>
              </div>
              <div className="model-spec-card">
                <strong>FFA-Net (Dehazing)</strong>
                <p>Input: 640 x 640</p>
                <p>PSNR: 24.8 dB</p>
                <p>SSIM: 0.88</p>
                <p>Enhancement: 32 ms/frame</p>
              </div>
            </div>
          </BorderGlow>
        </article>

        <article>
          <BorderGlow className="panel glass">
            <ShinyText text="Pothole Pipeline Model Specifications" className="text-xl font-bold mb-3" color="#ffffff" shineColor="#ffffff" />
            <div className="model-spec-grid">
              <div className="model-spec-card">
                <strong>YOLOv8 (Pothole Detection)</strong>
                <p>Artifact: yolov8n.pt</p>
                <p>mAP@50: 0.89</p>
                <p>Precision / Recall: 0.9 / 0.87</p>
                <p>Inference: 24 ms/frame</p>
              </div>
              <div className="model-spec-card">
                <strong>XGBoost (Severity Scoring)</strong>
                <p>Target: Severity Index (0-100)</p>
                <p>R2 Score: 0.82</p>
                <p>MAE: 4.7</p>
                <p>Inference: 2.8 ms/sample</p>
              </div>
              <div className="model-spec-card">
                <strong>FFA-Net (Contrast Stabilizer)</strong>
                <p>Purpose: Low-visibility enhancement</p>
                <p>PSNR Gain: +3.4 dB</p>
                <p>SSIM Gain: +0.07</p>
                <p>Enhancement: 29 ms/frame</p>
              </div>
            </div>
          </BorderGlow>
        </article>
      </section>
    </div>
  )
}
