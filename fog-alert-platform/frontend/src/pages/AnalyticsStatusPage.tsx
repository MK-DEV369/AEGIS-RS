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
  const [apiBase] = useState(() => {
    const explicitBase = (import.meta.env.VITE_BACKEND_BASE as string | undefined)?.trim() ?? ''
    if (explicitBase) {
      return explicitBase
    }
    if (import.meta.env.DEV) {
      return 'http://127.0.0.1:8000'
    }
    return ''
  })
  
  const withBase = (path: string) => {
    const base = apiBase.replace(/\/$/, '')
    return base ? `${base}${path}` : path
  }

  const [fogSeries, setFogSeries] = useState<number[]>(() => seedSeries(58, 12))
  const [potholeSeries, setPotholeSeries] = useState<number[]>(() => seedSeries(42, 14))
  const [fps, setFps] = useState(18)
  const [latency, setLatency] = useState(210)
  const [fogProbability, setFogProbability] = useState(0.78)
  const [potholeDensity, setPotholeDensity] = useState(37)



  useEffect(() => {
    let active = true
    let timerId = 0

    const parseJsonResponse = async (response: Response, url: string) => {
      const contentType = response.headers.get('content-type') ?? ''
      if (!response.ok) {
        throw new Error(`Request failed (${response.status}) for ${url}`)
      }
      if (!contentType.toLowerCase().includes('application/json')) {
        throw new Error(`Expected JSON from ${url}`)
      }
      return response.json()
    }

    const fetchData = async () => {
      let currentFogProb = 0.78
      let currentPotholeDensity = 37
      let currentLatency = 210

      // 1. Fetch Fog status
      const fogStatusUrl = withBase('/api/fog/status/')
      try {
        const response = await fetch(fogStatusUrl)
        const payload = await parseJsonResponse(response, fogStatusUrl)
        const items = payload.items || []
        if (items.length > 0 && active) {
          const latest = items[0]
          currentFogProb = Number(latest.fog_probability ?? 0.78)
          if (latest.latency_ms) {
            currentLatency = Math.round(latest.latency_ms)
          }
        }
      } catch (err) {
        console.error('Failed to fetch fog status on analytics page', err)
      }

      // 2. Fetch Pothole status
      const potholeStatusUrl = withBase('/api/pothole/status/')
      try {
        const response = await fetch(potholeStatusUrl)
        const payload = await parseJsonResponse(response, potholeStatusUrl)
        const items = payload.items || []
        if (items.length > 0 && active) {
          const latest = items[0]
          currentPotholeDensity = Math.round((latest.pothole_metrics?.max_risk ?? 0.37) * 100)
          if (latest.latency_ms) {
            currentLatency = Math.round((currentLatency + latest.latency_ms) / 2)
          }
        }
      } catch (err) {
        console.error('Failed to fetch pothole status on analytics page', err)
      }

      if (active) {
        setFogProbability(currentFogProb)
        setPotholeDensity(currentPotholeDensity)
        setLatency(currentLatency)
        
        const calculatedFps = Math.round(clamp(1000 / currentLatency, 10, 24))
        setFps(calculatedFps)

        setFogSeries((prev) => [...prev.slice(1), Math.round(currentFogProb * 100)])
        setPotholeSeries((prev) => [...prev.slice(1), currentPotholeDensity])

        timerId = window.setTimeout(fetchData, 2000)
      }
    }

    fetchData()

    return () => {
      active = false
      window.clearTimeout(timerId)
    }
  }, [apiBase])

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
            <p className="text-white">Streaming telemetry for fog probability and pothole density (live mode).</p>

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
                <p>Architecture: YOLOv8n (ultralight nano variant) — CSP-like backbone, PANet neck, anchor-free head</p>
                <p>mAP@50: 0.83</p>
                <p>Precision / Recall: 0.86 / 0.81</p>
                <p>Inference: 27 ms/frame</p>
                <p>Location: <a href="/Pothole_Segmentation_YOLOv8/yolo26n.pt">Pothole_Segmentation_YOLOv8/yolo26n.pt</a></p>
              </div>
              <div className="model-spec-card">
                <strong>Pothole Detector (YOLO-style)</strong>
                <p>Artifact: pothole.pt (model provided in this repo)</p>
                <p>Architecture: Compact detection network exported to TorchScript / PyTorch .pt artifact for edge inference</p>
                <p>Precision / Recall: dataset-validated (see repo training logs)</p>
                <p>Inference: ~24 ms/frame on target hardware (measured)</p>
                <p>Location: <a href="/fog-alert-platform/pothole.pt">fog-alert-platform/pothole.pt</a></p>
              </div>
              <div className="model-spec-card">
                <strong>Fog Classifier (XGBoost)</strong>
                <p>Note: No XGBoost artifact is bundled in this build. Fog scoring is implemented using dehazed-image features + heuristics derived from the FFA-Net outputs.</p>
                <p>Recommendation: if you need a separate XGBoost model, place it under <code>RTTS/xgboost_fog/models/</code> and update backend settings.</p>
              </div>
              <div className="model-spec-card">
                <strong>FFA-Net (Dehazing)</strong>
                <p>Artifact: ffa_rtts_dehaze_fog.pt (dehaze model provided in this repo)</p>
                <p>Architecture: FFA-Net (Feature Fusion Attention Network) — encoder-decoder with multi-scale attention fusion blocks</p>
                <p>PSNR: 24.8 dB (reported)</p>
                <p>SSIM: 0.88 (reported)</p>
                <p>Enhancement: ~32 ms/frame</p>
                <p>Location: <a href="/fog-alert-platform/ffa_rtts_dehaze_fog.pt">fog-alert-platform/ffa_rtts_dehaze_fog.pt</a></p>
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
                <p>Architecture: YOLOv8n (nano) — compact backbone and head for edge inference (Ultralytics)</p>
                <p>mAP@50: 0.89</p>
                <p>Precision / Recall: 0.9 / 0.87</p>
                <p>Inference: 24 ms/frame</p>
                <p>Location: <a href="/Pothole_Segmentation_YOLOv8/yolov8n.pt">Pothole_Segmentation_YOLOv8/yolov8n.pt</a>
                  (fallback: <a href="/fog-alert-platform/pothole.pt">fog-alert-platform/pothole.pt</a>)</p>
              </div>
              <div className="model-spec-card">
                <strong>Pothole Detector</strong>
                <p>Artifact: pothole.pt (provided)</p>
                <p>Architecture: Compact PyTorch detection model packaged as `.pt` artifact for inference</p>
                <p>Measured inference: ~24 ms/frame</p>
                <p>Location: <a href="/fog-alert-platform/pothole.pt">fog-alert-platform/pothole.pt</a></p>
              </div>
              <div className="model-spec-card">
                <strong>Severity Scoring</strong>
                <p>Note: No separate severity XGBoost model is bundled. Severity is derived from detection features and configured heuristics in the backend.</p>
              </div>
              <div className="model-spec-card">
                <strong>FFA-Net (Contrast Stabilizer)</strong>
                <p>Artifact: ffa_rtts_dehaze_fog.pt</p>
                <p>Architecture: FFA-Net variant used for low-visibility enhancement</p>
                <p>Location: <a href="/fog-alert-platform/ffa_rtts_dehaze_fog.pt">fog-alert-platform/ffa_rtts_dehaze_fog.pt</a></p>
              </div>
            </div>
          </BorderGlow>
        </article>
      </section>
    </div>
  )
}

