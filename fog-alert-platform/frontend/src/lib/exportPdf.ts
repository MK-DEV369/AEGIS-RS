/**
 * AEGIS-RS PDF Report Exporter
 * Academic LaTeX-style layout — light mode, Times serif body font.
 */
import jsPDF from 'jspdf'

// ─── Layout constants (all in mm) ────────────────────────────────────────────
const ML = 25          // left margin
const MR = 185         // right edge (210 - 25)
const TW = MR - ML     // text width  = 160 mm
const MT = 25          // top margin  (body start)
const MB = 272         // bottom limit before footer

// ─── Colour palette (light / LaTeX-inspired) ─────────────────────────────────
const BLK  : [number,number,number] = [12,  12,  12 ]   // near-black body
const DGRAY : [number,number,number] = [55,  55,  55 ]   // dark gray labels
const MGRAY : [number,number,number] = [110, 110, 110]   // medium gray
const LGRAY : [number,number,number] = [220, 220, 220]   // rule / border
const LLGRAY: [number,number,number] = [245, 245, 245]   // table alt row
const WHITE : [number,number,number] = [255, 255, 255]
const ACAD  : [number,number,number] = [25,  65,  140]   // deep blue accent (like IEEE)
const RED   : [number,number,number] = [180, 20,  20 ]
const ORG   : [number,number,number] = [170, 90,  0  ]
const GRN   : [number,number,number] = [20,  120, 50 ]

// ─── Helpers ─────────────────────────────────────────────────────────────────
const setC = (doc: jsPDF, c: [number,number,number]) => doc.setTextColor(...c)
const setF = (doc: jsPDF, c: [number,number,number]) => doc.setFillColor(...c)
const setD = (doc: jsPDF, c: [number,number,number]) => doc.setDrawColor(...c)

function sevColor(s: string): [number,number,number] {
  const u = (s ?? '').toUpperCase()
  if (u === 'HIGH' || u === 'CRITICAL') return RED
  if (u === 'MEDIUM')                   return ORG
  return GRN
}

// ─── Horizontal rule ──────────────────────────────────────────────────────────
function rule(doc: jsPDF, y: number, thick = 0.25, color = LGRAY): number {
  setD(doc, color)
  doc.setLineWidth(thick)
  doc.line(ML, y, MR, y)
  return y + 1.5
}

function doubleRule(doc: jsPDF, y: number): number {
  setD(doc, ACAD)
  doc.setLineWidth(0.6)
  doc.line(ML, y, MR, y)
  doc.setLineWidth(0.2)
  doc.line(ML, y + 1.2, MR, y + 1.2)
  return y + 3
}

// ─── Section header (LaTeX \section style) ────────────────────────────────────
let _sectionCounter = 0

function section(doc: jsPDF, y: number, title: string, noNumber = false): number {
  if (!noNumber) _sectionCounter++
  const label = noNumber ? title : `${_sectionCounter}.  ${title}`
  y = checkBreak(doc, y, 18)
  doc.setFont('times', 'bold')
  doc.setFontSize(13)
  setC(doc, ACAD)
  doc.text(label.toUpperCase(), ML, y)
  y += 1.5
  y = rule(doc, y, 0.4, ACAD)
  return y + 2
}

// ─── Subsection header (\subsection) ─────────────────────────────────────────
function subsection(doc: jsPDF, y: number, title: string): number {
  y = checkBreak(doc, y, 12)
  doc.setFont('times', 'bolditalic')
  doc.setFontSize(10.5)
  setC(doc, BLK)
  doc.text(title, ML, y)
  y += 1
  rule(doc, y, 0.15, LGRAY)
  return y + 3.5
}

// ─── Body text ────────────────────────────────────────────────────────────────
function body(doc: jsPDF, y: number, text: string, color = BLK, size = 10): number {
  doc.setFont('times', 'normal')
  doc.setFontSize(size)
  setC(doc, color)
  const lines = doc.splitTextToSize(text, TW) as string[]
  doc.text(lines, ML, y)
  return y + lines.length * (size * 0.4) + 1
}

// ─── Key-value detail row ─────────────────────────────────────────────────────
function kvRow(doc: jsPDF, y: number, key: string, value: string, valColor = BLK, xBase = ML): number {
  doc.setFont('times', 'bold')
  doc.setFontSize(9.5)
  setC(doc, DGRAY)
  doc.text(key, xBase, y)

  doc.setFont('times', 'normal')
  setC(doc, valColor)
  // Truncate value to fit remaining column width
  const maxW = MR - xBase - 58
  const truncVal = doc.splitTextToSize(value, maxW)[0] as string
  doc.text(truncVal, xBase + 57, y)
  return y + 6
}

// ─── Two-column KPI block ─────────────────────────────────────────────────────
function kpiBlock(
  doc: jsPDF, y: number,
  items: Array<{ label: string; value: string; color?: [number,number,number] }>,
  cols = 4
): number {
  const colW = TW / cols
  const boxH = 18

  items.forEach((item, i) => {
    const col = i % cols
    const row = Math.floor(i / cols)
    const x = ML + col * colW
    const by = y + row * (boxH + 3)

    // Box outline
    setF(doc, LLGRAY)
    setD(doc, LGRAY)
    doc.setLineWidth(0.2)
    doc.rect(x + 1, by, colW - 2, boxH, 'FD')

    // Label
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7)
    setC(doc, MGRAY)
    doc.text(item.label.toUpperCase(), x + colW / 2, by + 6, { align: 'center' })

    // Value
    doc.setFont('times', 'bold')
    doc.setFontSize(12)
    setC(doc, item.color ?? BLK)
    doc.text(item.value, x + colW / 2, by + 14, { align: 'center' })
  })

  const rows = Math.ceil(items.length / cols)
  return y + rows * (boxH + 3) + 4
}

// ─── Booktabs-style table ─────────────────────────────────────────────────────
function booktabs(
  doc: jsPDF, y: number,
  headers: string[],
  rows: string[][],
  colW: number[],
  maxRows = 20
): number {
  const rowH = 6.5

  // \toprule
  setD(doc, BLK)
  doc.setLineWidth(0.5)
  doc.line(ML, y, MR, y)
  y += 0.5

  // Header row
  let cx = ML
  headers.forEach((h, i) => {
    doc.setFont('times', 'bold')
    doc.setFontSize(9)
    setC(doc, BLK)
    doc.text(h, cx + 1, y + 5)
    cx += colW[i]
  })
  y += rowH

  // \midrule
  setD(doc, BLK)
  doc.setLineWidth(0.25)
  doc.line(ML, y, MR, y)
  y += 0.5

  // Data rows
  const visible = rows.slice(0, maxRows)
  visible.forEach((row, ri) => {
    // Alternating shading
    if (ri % 2 === 1) {
      setF(doc, LLGRAY)
      doc.rect(ML, y, TW, rowH - 0.5, 'F')
    }
    cx = ML
    row.forEach((cell, ci) => {
      doc.setFont('times', 'normal')
      doc.setFontSize(8.5)
      setC(doc, BLK)
      const maxChars = Math.floor(colW[ci] / 2.1)
      const txt = String(cell).length > maxChars ? String(cell).slice(0, maxChars - 1) + '…' : String(cell)
      doc.text(txt, cx + 1, y + 4.5)
      cx += colW[ci]
    })
    y += rowH
  })

  // \bottomrule
  setD(doc, BLK)
  doc.setLineWidth(0.5)
  doc.line(ML, y, MR, y)
  y += 0.5

  if (rows.length > maxRows) {
    doc.setFont('times', 'italic')
    doc.setFontSize(8)
    setC(doc, MGRAY)
    doc.text(`(${rows.length - maxRows} additional rows omitted for brevity)`, ML, y + 4)
    y += 7
  }

  return y + 4
}

// ─── Page break helper ────────────────────────────────────────────────────────
function checkBreak(doc: jsPDF, y: number, needed = 35): number {
  if (y + needed > MB) {
    return newPage(doc)
  }
  return y
}

// ─── Header / running head ────────────────────────────────────────────────────
function drawRunningHead(doc: jsPDF, title: string) {
  doc.setFont('times', 'italic')
  doc.setFontSize(8)
  setC(doc, MGRAY)
  doc.text('AEGIS-RS System Intelligence Report', ML, 15)
  doc.text(title, MR, 15, { align: 'right' })
  setD(doc, LGRAY)
  doc.setLineWidth(0.2)
  doc.line(ML, 17, MR, 17)
}

// ─── New page factory ─────────────────────────────────────────────────────────
let _pageSection = 'Overview'

function newPage(doc: jsPDF, sectionTitle?: string): number {
  doc.addPage()
  setF(doc, WHITE)
  doc.rect(0, 0, 210, 297, 'F')
  if (sectionTitle) _pageSection = sectionTitle
  drawRunningHead(doc, _pageSection)
  return MT + 4
}

// ─── Footer on every page ─────────────────────────────────────────────────────
function stampFooters(doc: jsPDF, total: number, ts: string) {
  for (let p = 1; p <= total; p++) {
    doc.setPage(p)
    if (p === 1) continue  // cover page gets no running footer
    setD(doc, LGRAY)
    doc.setLineWidth(0.2)
    doc.line(ML, 280, MR, 280)
    doc.setFont('times', 'normal')
    doc.setFontSize(8)
    setC(doc, MGRAY)
    doc.text(`AEGIS-RS Confidential Report  ·  ${ts}`, ML, 285)
    doc.text(`${p}`, MR, 285, { align: 'right' })
  }
}

// ─── Cover / Title page ───────────────────────────────────────────────────────
function drawTitlePage(doc: jsPDF, ts: string) {
  setF(doc, WHITE)
  doc.rect(0, 0, 210, 297, 'F')

  // Top accent band (thin)
  setF(doc, ACAD)
  doc.rect(0, 0, 210, 1.2, 'F')

  // Institution-style logo area
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(9)
  setC(doc, ACAD)
  doc.text('AUTONOMOUS EDGE GUARD FOR INTELLIGENT SAFETY — ROAD SAFETY', 105, 28, { align: 'center' })

  setD(doc, ACAD)
  doc.setLineWidth(0.4)
  doc.line(ML, 31, MR, 31)
  doc.setLineWidth(0.15)
  doc.line(ML, 32.5, MR, 32.5)

  // Main title  (like \title in LaTeX)
  doc.setFont('times', 'bold')
  doc.setFontSize(26)
  setC(doc, BLK)
  doc.text('AEGIS-RS', 105, 62, { align: 'center' })

  doc.setFont('times', 'normal')
  doc.setFontSize(14)
  setC(doc, DGRAY)
  doc.text('System Intelligence & Telemetry Report', 105, 74, { align: 'center' })

  // Thin rule under title
  rule(doc, 80, 0.25, LGRAY)

  // Abstract-style blurb
  doc.setFont('times', 'italic')
  doc.setFontSize(10)
  setC(doc, DGRAY)
  const abstract =
    'This report presents a consolidated snapshot of real-time sensor telemetry, ' +
    'AI-driven road-hazard detection, and V2V/I2V alert dissemination captured by the ' +
    'AEGIS-RS embedded platform. Data is sourced directly from live backend API endpoints ' +
    'and reflects system state at the time of export.'
  const absLines = doc.splitTextToSize(abstract, 130) as string[]
  doc.text(absLines, 105, 92, { align: 'center' })

  // Metadata table (like LaTeX \author / \date block)
  const metaY = 130
  const metaRows: Array<[string, string]> = [
    ['Report Generated', ts],
    ['System',           'AEGIS-RS v2.0 — Combined AI Pipeline'],
    ['Models',           'FFA-Net (Dehazing & Fog Classification), YOLOv8 (Pothole Detection)'],
    ['Communication',    'ESP-NOW V2V/I2V via ESP32 OBU/RSU nodes'],
    ['Classification',   'Internal / Academic Project Use Only'],
  ]

  setD(doc, LGRAY)
  doc.setLineWidth(0.2)
  doc.rect(ML + 10, metaY - 5, TW - 20, metaRows.length * 9 + 10, 'S')

  metaRows.forEach(([k, v], i) => {
    const my = metaY + i * 9

    doc.setFont('times', 'bold')
    doc.setFontSize(9)
    setC(doc, DGRAY)
    doc.text(k, ML + 14, my + 1)

    doc.setFont('times', 'normal')
    setC(doc, BLK)
    const vLines = doc.splitTextToSize(v, 95) as string[]
    doc.text(vLines, ML + 70, my + 1)
  })

  // Contents preview
  const tocY = 225
  doc.setFont('times', 'bold')
  doc.setFontSize(10)
  setC(doc, BLK)
  doc.text('Contents', ML, tocY)
  rule(doc, tocY + 2, 0.2, LGRAY)

  const toc = [
    ['1.', 'Live System Overview', '2'],
    ['2.', 'Fog Analysis',         '2'],
    ['3.', 'Pothole Analysis',      '2'],
    ['4.', 'Fog Detection History', '3'],
    ['5.', 'Pothole History',       '4'],
    ['6.', 'Active System Alerts',  '5'],
    ['7.', 'ESP32 RSU Telemetry',   '5'],
    ['8.', 'Summary & Recommendations', '6'],
  ]
  toc.forEach(([num, title, pg], i) => {
    const ty = tocY + 7 + i * 6
    doc.setFont('times', 'normal')
    doc.setFontSize(9)
    setC(doc, BLK)
    doc.text(`${num}  ${title}`, ML + 4, ty)

    // Leader dots
    const dots = '.'.repeat(60)
    setC(doc, LGRAY)
    doc.text(dots, ML + 10, ty)

    setC(doc, BLK)
    doc.text(pg, MR - 2, ty, { align: 'right' })
  })

  // Bottom rule
  setF(doc, ACAD)
  doc.rect(0, 295.5, 210, 1.5, 'F')
}

// ─── Exported types ───────────────────────────────────────────────────────────
export interface ReportData {
  fogLevel?: string
  fogProbability?: number
  fogSmoothed?: number
  fogVisibility?: number
  fogContrast?: number
  fogRiskScore?: number
  maxRisk?: number
  criticalCount?: number
  highCount?: number
  detectionsAnalyzed?: number
  potholeCount?: number
  totalPotholes?: number
  potholeLocation?: string
  alerts?: Array<{
    id: string
    type?: string
    severity: string
    status?: string
    location: string
    detected_at?: string
    details?: string
    visibility?: string
  }>
  telemetryList?: Array<Record<string, string>>
  potholeHistory?: Array<Record<string, any>>
  fogHistory?: Array<Record<string, any>>
}

// ─── Main export entry point ──────────────────────────────────────────────────
export async function exportReportAsPdf(data: ReportData): Promise<void> {
  _sectionCounter = 0   // reset counter for each export

  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
  const now = new Date()
  const ts  = now.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false })

  // White base for page 1
  setF(doc, WHITE)
  doc.rect(0, 0, 210, 297, 'F')

  // ── Title page ────────────────────────────────────────────────────────────
  drawTitlePage(doc, ts)

  // ── Page 2: System Overview + Fog + Pothole Analysis ─────────────────────
  let y = newPage(doc, 'System Overview')

  const adasRisk  = Math.max(data.maxRisk ?? 0, data.fogRiskScore ?? 0)
  const riskColor = adasRisk > 0.7 ? RED : adasRisk > 0.4 ? ORG : GRN
  const fogColor  = (data.fogLevel === 'HIGH') ? RED : (data.fogLevel === 'MEDIUM') ? ORG : GRN

  y = section(doc, y, 'Live System Overview')

  y = kpiBlock(doc, y, [
    { label: 'ADAS Max Risk',   value: adasRisk.toFixed(3),                       color: riskColor },
    { label: 'Fog Level',       value: data.fogLevel ?? 'LOW',                    color: fogColor  },
    { label: 'Visibility',      value: `${(data.fogVisibility ?? 0).toFixed(0)} m`               },
    { label: 'Total Potholes',  value: String(data.totalPotholes ?? 0),            color: ACAD     },
  ], 4)

  y = kpiBlock(doc, y, [
    { label: 'Fog Probability', value: (data.fogProbability ?? 0).toFixed(3) },
    { label: 'Smoothed Prob.',  value: (data.fogSmoothed    ?? 0).toFixed(3) },
    { label: 'Image Contrast',  value: (data.fogContrast    ?? 0).toFixed(3) },
    { label: 'Fog Risk Score',  value: (data.fogRiskScore   ?? 0).toFixed(3), color: riskColor },
  ], 4)

  y = kpiBlock(doc, y, [
    { label: 'Critical Potholes', value: String(data.criticalCount ?? 0), color: RED  },
    { label: 'High Potholes',     value: String(data.highCount     ?? 0), color: ORG  },
    { label: 'Frames Analyzed',   value: String(data.detectionsAnalyzed ?? 0)         },
    { label: 'Current Frame',     value: `${data.potholeCount ?? 0} det.`             },
  ], 4)

  y += 2
  y = checkBreak(doc, y, 50)

  // ── Section 2: Fog Analysis ───────────────────────────────────────────────
  y = section(doc, y, 'Fog Analysis')

  const fogRows: Array<[string, string, [number,number,number]?]> = [
    ['Detection Level',       data.fogLevel        ?? 'N/A',                      fogColor  ],
    ['Fog Probability (raw)', (data.fogProbability ?? 0).toFixed(6),              BLK       ],
    ['Smoothed Probability',  (data.fogSmoothed    ?? 0).toFixed(6),              BLK       ],
    ['Estimated Visibility',  `${(data.fogVisibility ?? 0).toFixed(2)} m`,        BLK       ],
    ['Image Contrast (RMS)',  (data.fogContrast    ?? 0).toFixed(6),              BLK       ],
    ['Fog Risk Score',        (data.fogRiskScore   ?? 0).toFixed(6),              riskColor ],
  ]

  // Proper two-column layout: left column at ML, right column at midpage
  const COL_R = ML + 82          // right column x start = 107 mm
  const half  = Math.ceil(fogRows.length / 2)
  const leftFog  = fogRows.slice(0, half)
  const rightFog = fogRows.slice(half)

  // Draw column divider hairline
  setD(doc, LGRAY)
  doc.setLineWidth(0.15)
  doc.line(COL_R - 3, y, COL_R - 3, y + half * 6 + 2)

  const startY = y
  leftFog.forEach(([k, v, c])  => { y  = kvRow(doc, y,       k, v, c, ML) })
  let ry = startY
  rightFog.forEach(([k, v, c]) => { ry = kvRow(doc, ry, k, v, c, COL_R) })
  y = Math.max(y, ry) + 5

  // ── Section 3: Pothole Analysis ───────────────────────────────────────────
  y = checkBreak(doc, y, 50)
  y = section(doc, y, 'Pothole Analysis')

  const phRows: Array<[string, string, [number,number,number]?]> = [
    ['Max Risk Score',          (data.maxRisk            ?? 0).toFixed(6), riskColor ],
    ['Critical Detections',     String(data.criticalCount ?? 0),           RED       ],
    ['High Detections',         String(data.highCount     ?? 0),           ORG       ],
    ['Frames Analyzed',         String(data.detectionsAnalyzed ?? 0),      BLK       ],
    ['Current Frame Count',     String(data.potholeCount  ?? 0),           BLK       ],
    ['Cumulative Total',        String(data.totalPotholes ?? 0),           ACAD      ],
    ['GPS Location',            data.potholeLocation ?? 'N/A',             BLK       ],
    ['Combined ADAS Risk',      adasRisk.toFixed(6),                       riskColor ],
  ]

  // Single-column layout — 8 rows fits cleanly without any overlap risk
  phRows.forEach(([k, v, c]) => { y = kvRow(doc, y, k, v, c, ML) })
  y += 4

  // ── Page 3: Fog History ───────────────────────────────────────────────────
  y = newPage(doc, 'Detection History')
  y = section(doc, y, 'Fog Detection History')

  if (data.fogHistory && data.fogHistory.length > 0) {
    y = body(doc, y,
      `Table 1 presents the ${Math.min(data.fogHistory.length, 20)} most recent fog detection ` +
      'records retrieved from the backend in descending chronological order.',
      DGRAY, 9)
    y += 2

    // Table caption
    doc.setFont('times', 'bolditalic')
    doc.setFontSize(8.5)
    setC(doc, DGRAY)
    doc.text('Table 1: Recent Fog Detection Records', ML, y)
    y += 4

    const fogTableRows = data.fogHistory.slice(0, 20).map((r: any) => [
      r.created_at ? new Date(r.created_at).toLocaleTimeString('en-IN') : '-',
      r.fog_level ?? '-',
      Number(r.fog_probability ?? 0).toFixed(4),
      `${Number(r.visibility_meters ?? 0).toFixed(1)} m`,
      Number(r.contrast ?? 0).toFixed(4),
      Number(r.risk_score ?? 0).toFixed(4),
    ])
    y = booktabs(doc, y,
      ['Timestamp', 'Level', 'Probability', 'Visibility', 'Contrast', 'Risk Score'],
      fogTableRows,
      [30, 22, 28, 28, 26, 26], 20)
  } else {
    y = body(doc, y, 'No fog detection history is currently available.', MGRAY, 9)
  }

  // ── Section 5: Pothole History ────────────────────────────────────────────
  y = checkBreak(doc, y, 55)
  y = section(doc, y, 'Pothole Detection History')

  if (data.potholeHistory && data.potholeHistory.length > 0) {
    y = body(doc, y,
      `Table 2 lists the ${Math.min(data.potholeHistory.length, 20)} most recent pothole ` +
      'detection frames recorded by the combined camera pipeline.',
      DGRAY, 9)
    y += 2

    doc.setFont('times', 'bolditalic')
    doc.setFontSize(8.5)
    setC(doc, DGRAY)
    doc.text('Table 2: Recent Pothole Detection Frames', ML, y)
    y += 4

    const phTableRows = data.potholeHistory.slice(0, 20).map((r: any) => [
      r.created_at ? new Date(r.created_at).toLocaleTimeString('en-IN') : '-',
      r.source_id ?? '-',
      String(r.pothole_count  ?? 0),
      String(r.total_potholes ?? 0),
      Number(r.pothole_metrics?.max_risk      ?? 0).toFixed(3),
      String(r.pothole_metrics?.critical_count ?? 0),
    ])
    y = booktabs(doc, y,
      ['Timestamp', 'Source', 'Count', 'Cumulative', 'Max Risk', 'Critical'],
      phTableRows,
      [30, 42, 18, 24, 26, 20], 20)
  } else {
    y = body(doc, y, 'No pothole history is currently available.', MGRAY, 9)
  }

  // ── Page 4: Alerts ────────────────────────────────────────────────────────
  y = newPage(doc, 'Active Alerts')
  y = section(doc, y, 'Active System Alerts')

  if (data.alerts && data.alerts.length > 0) {
    y = body(doc, y,
      `A total of ${data.alerts.length} alert(s) are currently active across both fog and ` +
      'pothole detection subsystems. Table 3 provides a consolidated view, followed by ' +
      'individual alert descriptions.',
      DGRAY, 9)
    y += 2

    doc.setFont('times', 'bolditalic')
    doc.setFontSize(8.5)
    setC(doc, DGRAY)
    doc.text('Table 3: Active Alert Register', ML, y)
    y += 4

    const alertTableRows = data.alerts.slice(0, 20).map(a => [
      (a.type ?? 'UNKNOWN').toUpperCase(),
      a.severity,
      a.status ?? '-',
      a.location,
      a.visibility ?? '-',
      a.detected_at ? new Date(a.detected_at).toLocaleTimeString('en-IN') : '-',
    ])
    y = booktabs(doc, y,
      ['Type', 'Severity', 'Status', 'Location', 'Visibility', 'Time'],
      alertTableRows,
      [22, 22, 26, 48, 20, 22], 20)

    // Individual alert descriptions
    y = checkBreak(doc, y, 20)
    y = subsection(doc, y, '6.1  Alert Descriptions')

    data.alerts.slice(0, 8).forEach((a, i) => {
      y = checkBreak(doc, y, 20)
      const sc = sevColor(a.severity)

      doc.setFont('times', 'bold')
      doc.setFontSize(9.5)
      setC(doc, sc)
      doc.text(
        `[${a.severity}]  ${(a.type ?? 'ALERT').toUpperCase()}  —  ${a.location}`,
        ML, y
      )
      y += 5

      doc.setFont('times', 'normal')
      doc.setFontSize(9)
      setC(doc, BLK)
      const detailLines = doc.splitTextToSize(a.details ?? 'No additional details.', TW - 6) as string[]
      doc.text(detailLines, ML + 3, y)
      y += detailLines.length * 4 + 4
      rule(doc, y, 0.15, LGRAY)
      y += 3
    })
  } else {
    y = body(doc, y, 'No active alerts are currently recorded in the system.', MGRAY, 9)
  }

  // ── Section 7: Telemetry ──────────────────────────────────────────────────
  if (data.telemetryList && data.telemetryList.length > 0) {
    y = checkBreak(doc, y, 55)
    y = section(doc, y, 'ESP32 RSU Telemetry Log')

    y = body(doc, y,
      'Table 4 records RSU_ALERT JSON payloads received from the ESP32 serial relay daemon. ' +
      'Each row corresponds to a disseminated OBU alert packet.',
      DGRAY, 9)
    y += 2

    doc.setFont('times', 'bolditalic')
    doc.setFontSize(8.5)
    setC(doc, DGRAY)
    doc.text('Table 4: ESP32 RSU Telemetry Payloads', ML, y)
    y += 4

    const telRows = data.telemetryList.slice(0, 15).map(t => [
      t.vehicle_id ?? 'OBU_001',
      t.severity   ?? '-',
      t.depth_cm   ?? '-',
      t.speed      ?? '0',
      t.lat        ?? '-',
      t.lng        ?? '-',
      t.status     ?? 'DISSEMINATED',
    ])
    y = booktabs(doc, y,
      ['Vehicle ID', 'Severity', 'Depth (cm)', 'Speed', 'Latitude', 'Longitude', 'Status'],
      telRows,
      [26, 22, 22, 16, 26, 26, 22], 15)
  }

  // ── Page 5: Summary ───────────────────────────────────────────────────────
  y = newPage(doc, 'Summary')
  y = section(doc, y, 'Summary and Recommendations')

  y = body(doc, y,
    'This section consolidates the key findings from the current monitoring session and ' +
    'presents automated recommendations generated by the AEGIS-RS risk engine based on ' +
    'the observed sensor data.',
    DGRAY, 9.5)
  y += 4

  y = subsection(doc, y, '8.1  Key Findings')

  const findings: Array<[string, string]> = [
    ['Report Timestamp',    ts],
    ['Fog Classification',  `${data.fogLevel ?? 'LOW'} (Probability: ${(data.fogProbability ?? 0).toFixed(4)})`],
    ['Estimated Visibility',`${(data.fogVisibility ?? 0).toFixed(1)} m`],
    ['ADAS Combined Risk',  adasRisk.toFixed(4)],
    ['Total Potholes',      String(data.totalPotholes ?? 0)],
    ['Critical Potholes',   String(data.criticalCount ?? 0)],
    ['High Potholes',       String(data.highCount ?? 0)],
    ['Active Alerts',       String(data.alerts?.length ?? 0)],
  ]

  findings.forEach(([k, v]) => { y = kvRow(doc, y, k, v) })
  y += 4

  y = subsection(doc, y, '8.2  Automated Recommendations')

  const recs: string[] = []
  if ((data.fogVisibility ?? 1000) < 100)
    recs.push('Fog visibility is below 100 m. The RSU should broadcast a reduced-speed advisory via ESP-NOW to all V2V-capable OBU nodes in range.')
  if (adasRisk > 0.7)
    recs.push('ADAS combined risk exceeds the critical threshold (0.70). Immediate alert dissemination to infrastructure nodes is recommended.')
  if ((data.criticalCount ?? 0) > 0)
    recs.push(`${data.criticalCount} critical pothole(s) detected. Road maintenance dispatch should be initiated without delay.`)
  if ((data.highCount ?? 0) > 2)
    recs.push(`${data.highCount} high-severity potholes detected. A temporary speed restriction advisory is recommended for the affected corridor.`)
  if (recs.length === 0)
    recs.push('All monitored parameters are within nominal operating bounds. Continued surveillance is advised.')

  recs.forEach((r, i) => {
    y = checkBreak(doc, y, 18)
    doc.setFont('times', 'bold')
    doc.setFontSize(9.5)
    setC(doc, ACAD)
    doc.text(`R${i + 1}.`, ML, y)

    doc.setFont('times', 'normal')
    setC(doc, BLK)
    const rLines = doc.splitTextToSize(r, TW - 10) as string[]
    doc.text(rLines, ML + 8, y)
    y += rLines.length * 5 + 3
  })

  // ── Final double rule + end matter ────────────────────────────────────────
  y += 4
  y = checkBreak(doc, y, 20)
  doubleRule(doc, y)
  y += 6

  doc.setFont('times', 'italic')
  doc.setFontSize(8.5)
  setC(doc, MGRAY)
  doc.text(
    'End of Report. Generated automatically by the AEGIS-RS AI pipeline. ' +
    'Data reflects live system state at the time of export.',
    105, y, { align: 'center', maxWidth: TW }
  )

  // ── Footers on all non-cover pages ────────────────────────────────────────
  stampFooters(doc, doc.getNumberOfPages(), ts)

  // ── Save ──────────────────────────────────────────────────────────────────
  const fn = `AEGIS-RS_Report_${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}${String(now.getDate()).padStart(2,'0')}_${String(now.getHours()).padStart(2,'0')}${String(now.getMinutes()).padStart(2,'0')}.pdf`
  doc.save(fn)
}
