/**
 * ExportReportButton
 * Fetches all live data from the backend APIs and generates an AEGIS-RS PDF report.
 */
import { useState } from 'react'
import { exportReportAsPdf, type ReportData } from '@/lib/exportPdf'

interface Props {
  apiBase: string
  /** Current live state passed from the parent monitoring/dashboard page */
  liveData?: Partial<ReportData>
}

export function ExportReportButton({ apiBase, liveData = {} }: Props) {
  const [loading, setLoading] = useState(false)
  const [done, setDone]       = useState(false)

  const withBase = (path: string) => {
    const base = apiBase.replace(/\/$/, '')
    return base ? `${base}${path}` : path
  }

  const safeJson = async (url: string) => {
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(5000) })
      if (!r.ok) return null
      const ct = r.headers.get('content-type') ?? ''
      if (!ct.includes('application/json')) return null
      return r.json()
    } catch {
      return null
    }
  }

  const handleExport = async () => {
    setLoading(true)
    setDone(false)

    try {
      // ── Fetch all live API data ────────────────────────────────────────────
      const [fogPayload, potholePayload, telemetryPayload] = await Promise.all([
        safeJson(withBase('/api/fog/status/')),
        safeJson(withBase('/api/pothole/status/')),
        safeJson(withBase('/api/telemetry/status/')),
      ])

      const fogItems     = Array.isArray(fogPayload?.items)     ? fogPayload.items     : []
      const potholeItems = Array.isArray(potholePayload?.items) ? potholePayload.items : []
      const telItems     = Array.isArray(telemetryPayload?.items) ? telemetryPayload.items : []

      const latestFog     = fogItems[0]     ?? {}
      const latestPothole = potholeItems[0] ?? {}
      const metrics       = latestPothole.pothole_metrics ?? {}
      const coords        = latestPothole.coordinates ?? {}

      // Build alert list from both fog + pothole records
      const alerts: ReportData['alerts'] = []

      fogItems.slice(0, 15).forEach((f: any) => {
        alerts!.push({
          id:          String(f.request_id ?? f.id ?? Math.random()),
          type:        'fog',
          severity:    f.fog_level ?? 'LOW',
          status:      f.fog_probability > 0.5 ? 'open' : 'monitoring',
          location:    `${f.coordinates?.lat ?? 'N/A'}, ${f.coordinates?.lng ?? 'N/A'}`,
          visibility:  f.visibility_meters != null ? `${Number(f.visibility_meters).toFixed(0)}m` : 'N/A',
          detected_at: f.created_at,
          details:     `Fog Level ${f.fog_level ?? 'LOW'} — Prob: ${Number(f.fog_probability ?? 0).toFixed(3)}, Contrast: ${Number(f.contrast ?? 0).toFixed(3)}`,
        })
      })

      potholeItems.slice(0, 15).forEach((p: any) => {
        if ((p.pothole_count ?? 0) === 0) return
        const mx = p.pothole_metrics?.max_risk ?? 0
        alerts!.push({
          id:          String(p.request_id ?? p.id ?? Math.random()),
          type:        'pothole',
          severity:    mx > 0.8 ? 'CRITICAL' : mx > 0.5 ? 'HIGH' : mx > 0.2 ? 'MEDIUM' : 'LOW',
          status:      'open',
          location:    `${p.coordinates?.lat ?? 'N/A'}, ${p.coordinates?.lng ?? 'N/A'}`,
          detected_at: p.created_at,
          details:     `${p.pothole_count} potholes detected. Max Risk: ${Number(mx).toFixed(3)}. Total: ${p.total_potholes}`,
        })
      })

      // Build report data merging live props + fresh API data
      const adasRisk = Math.max(
        liveData.maxRisk ?? Number(metrics.max_risk ?? 0),
        liveData.fogRiskScore ?? Number(latestFog.risk_score ?? 0)
      )

      const report: ReportData = {
        // Fog (prefer live data if available, else use history)
        fogLevel:          liveData.fogLevel        ?? latestFog.fog_level,
        fogProbability:    liveData.fogProbability  ?? Number(latestFog.fog_probability ?? 0),
        fogSmoothed:       liveData.fogSmoothed     ?? Number(latestFog.fog_probability_smoothed ?? 0),
        fogVisibility:     liveData.fogVisibility   ?? Number(latestFog.visibility_meters ?? 0),
        fogContrast:       liveData.fogContrast     ?? Number(latestFog.contrast ?? 0),
        fogRiskScore:      liveData.fogRiskScore    ?? Number(latestFog.risk_score ?? 0),
        // Pothole
        maxRisk:           liveData.maxRisk         ?? Number(metrics.max_risk ?? 0),
        criticalCount:     liveData.criticalCount   ?? Number(metrics.critical_count ?? 0),
        highCount:         liveData.highCount       ?? Number(metrics.high_count ?? 0),
        detectionsAnalyzed:liveData.detectionsAnalyzed ?? Number(metrics.detections_analyzed ?? 0),
        potholeCount:      liveData.potholeCount    ?? Number(latestPothole.pothole_count ?? 0),
        totalPotholes:     liveData.totalPotholes   ?? Number(latestPothole.total_potholes ?? 0),
        potholeLocation:   liveData.potholeLocation ?? (coords.lat && coords.lng ? `${coords.lat}, ${coords.lng}` : 'N/A'),
        // Alerts
        alerts,
        // History tables
        fogHistory:     fogItems.slice(0, 20),
        potholeHistory: potholeItems.slice(0, 20),
        // Telemetry
        telemetryList:  telItems.slice(0, 15).map((t: any) => ({
          vehicle_id: t.vehicle_id ?? 'OBU_001',
          severity:   t.severity   ?? '-',
          depth_cm:   String(t.depth_cm ?? '-'),
          speed:      String(t.speed    ?? 0),
          lat:        String(t.lat      ?? '-'),
          lng:        String(t.lng      ?? '-'),
          status:     t.status     ?? 'DISSEMINATED',
        })),
      }

      await exportReportAsPdf(report)
      setDone(true)
      setTimeout(() => setDone(false), 3000)
    } catch (err) {
      console.error('[ExportReportButton] Export failed:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      id="export-pdf-btn"
      type="button"
      onClick={handleExport}
      disabled={loading}
      style={{
        display:       'inline-flex',
        alignItems:    'center',
        gap:           '8px',
        padding:       '10px 20px',
        background:    done
          ? 'linear-gradient(135deg, rgba(68,255,136,0.18), rgba(68,255,136,0.08))'
          : loading
            ? 'rgba(255,255,255,0.06)'
            : 'linear-gradient(135deg, rgba(0,212,255,0.18), rgba(94,234,212,0.10))',
        border:        `1.5px solid ${done ? 'rgba(68,255,136,0.5)' : 'rgba(0,212,255,0.35)'}`,
        borderRadius:  '10px',
        color:         done ? '#44ff88' : '#00d4ff',
        fontSize:      '0.88em',
        fontWeight:    700,
        cursor:        loading ? 'wait' : 'pointer',
        letterSpacing: '0.03em',
        transition:    'all 0.2s ease',
        backdropFilter:'blur(8px)',
        boxShadow:     done
          ? '0 0 16px rgba(68,255,136,0.2)'
          : '0 0 16px rgba(0,212,255,0.12)',
        whiteSpace:    'nowrap',
      }}
      onMouseEnter={e => {
        if (!loading) {
          (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 0 24px rgba(0,212,255,0.30)'
          ;(e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-1px)'
        }
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 0 16px rgba(0,212,255,0.12)'
        ;(e.currentTarget as HTMLButtonElement).style.transform = 'translateY(0)'
      }}
    >
      {loading ? (
        <>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ animation: 'spin 1s linear infinite' }}>
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="32" strokeDashoffset="12" strokeLinecap="round" />
          </svg>
          Building Report…
        </>
      ) : done ? (
        <>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M5 13l4 4L19 7" stroke="#44ff88" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          PDF Saved!
        </>
      ) : (
        <>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <polyline points="14,2 14,8 20,8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <line x1="12" y1="18" x2="12" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            <polyline points="9,15 12,18 15,15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Export PDF Report
        </>
      )}
      <style>{`@keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }`}</style>
    </button>
  )
}
