import { motion } from 'framer-motion'
import LineWaves from '@/components/LineWaves'
import GradientText from '@/components/GradientText'
import SplashCursor from '@/components/SplashCursor'
import BorderGlow from '@/components/BorderGlow'

const objectives = [
  'Run low-latency multimodal hazard analytics for live road conditions.',
  'Unify fog prediction, pothole detection, and GPS sensor context into one decision pipeline.',
  'Track source health, latency, and request consistency for operational reliability.',
  'Generate actionable risk alerts that are immediately useful during field demos.',
]

const architecture = [
  {
    title: 'Capture Layer',
    detail: 'Phone camera streams and GPS sensor packets are ingested with stable source IDs.',
  },
  {
    title: 'Realtime Processing Layer',
    detail: 'Frame resizing, optional realtime dehaze skip, and chunk-safe ingestion optimize throughput under live load.',
  },
  {
    title: 'AI Inference Layer',
    detail: 'YOLOv8 performs pothole inference while XGBoost predicts fog probability using extracted visual features.',
  },
  {
    title: 'Risk and Monitoring Layer',
    detail: 'Combined outputs, latency metrics, GPS context, and source status drive explainable risk monitoring.',
  },
]

const methodologies = [
  'Model-first modular API design: fog-only, pothole-only, and combined inference routes.',
  'Realtime optimization strategy: dynamic frame constraints, configurable inference size, and optional half precision.',
  'Robust streaming protocol: direct image ingest plus chunked transfer support for unstable networks.',
  'Observability loop: request IDs, source-level counters, and runtime cache management for rapid debugging.',
  'Edge demo readiness: GPS sensor ingest integrated alongside vision inference.',
]

const team = [
  { name: 'Ahibhruth A', usn: '1RV23AI011', branch: 'AIML' },
  { name: 'L Moryakantha', usn: '1RV24AI406', branch: 'AIML' },
  { name: 'Pavan', usn: '1RV23EC196', branch: 'ECE' },
  { name: 'Srivatsa', usn: '1RV23ET050', branch: 'ETE' },
]

const stackGroups = [
  {
    title: 'AI and Vision',
    items: ['YOLOv8', 'XGBoost', 'OpenCV', 'PyTorch'],
  },
  {
    title: 'Backend and APIs',
    items: ['Django', 'Django REST Framework', 'Python', 'NumPy/Pandas'],
  },
  {
    title: 'Frontend and UX',
    items: ['React', 'TypeScript', 'Framer Motion', 'shadcn + Tailwind CSS'],
  },
  {
    title: 'Realtime and Devices',
    items: ['GPS Sensor Feed', 'IP Webcam Relay', 'Chunked Upload Protocol', 'Runtime Source Monitoring'],
  },
]

export function HomePage() {
  return (
    <div className="page home-page">
      <SplashCursor
        DENSITY_DISSIPATION={3.5}
        VELOCITY_DISSIPATION={2}
        PRESSURE={0.1}
        CURL={3}
        SPLAT_RADIUS={0.2}
        SPLAT_FORCE={6000}
        COLOR_UPDATE_SPEED={10}
        SHADING
        RAINBOW_MODE={false}
        COLOR="#A855F7"
      />

      <div className="home-bg-layer" aria-hidden="true">
        <LineWaves
          speed={0.3}
          innerLineCount={32}
          outerLineCount={36}
          warpIntensity={1}
          rotation={-45}
          edgeFadeWidth={0}
          colorCycleSpeed={1}
          brightness={0.2}
          color1="#ffffff"
          color2="#ffffff"
          color3="#ffffff"
          enableMouseInteraction
          mouseInfluence={2}
        />
      </div>
      <section className="grid two-col">
        <motion.article
          className=""
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.35 }}
          transition={{ duration: 0.45, delay: 0.05 }}
        >
          <BorderGlow className="panel glass">
            <GradientText className="text-2xl font-bold mb-3" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
              About the Project
            </GradientText>
            <p>
              AEGIS-RS is an AI-enabled road safety platform designed for realtime field monitoring. The system fuses
              camera-based hazard inference with GPS sensor ingestion, then serves unified risk signals through a
              low-latency backend architecture built for live demonstrations and operational scalability.
            </p>
            <div className="github-block">
              <strong>GitHub Repository</strong>
              <a href="https://github.com/MK-DEV369/AEGIS-RS" target="_blank" rel="noreferrer">
                https://github.com/MK-DEV369/AEGIS-RS
              </a>
            </div>
          </BorderGlow>
        </motion.article>

        <motion.article
          className=""
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.35 }}
          transition={{ duration: 0.45, delay: 0.12 }}
        >
          <BorderGlow className="panel glass">
            <GradientText className="text-2xl font-bold mb-3" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
              Objectives
            </GradientText>
            <ul className="bullet-list">
              {objectives.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </BorderGlow>
        </motion.article>
      </section>

      <motion.section
        className=""
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.3 }}
        transition={{ duration: 0.5 }}
      >
        <BorderGlow className="panel glass">
          <GradientText className="text-2xl font-bold mb-3" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
            Architecture
          </GradientText>
          <div className="flow">
            <div className="flow-node">Camera and GPS Sensor Inputs</div>
            <div className="flow-arrow">→</div>
            <div className="flow-node">Realtime Ingestion and Optimization</div>
            <div className="flow-arrow">→</div>
            <div className="flow-node">YOLOv8 + XGBoost Inference</div>
            <div className="flow-arrow">→</div>
            <div className="flow-node">Risk Fusion + Monitoring APIs</div>
          </div>
          <div className="team-list" style={{ marginTop: '14px' }}>
            {architecture.map((layer) => (
              <div key={layer.title} className="team-card">
                <strong>{layer.title}</strong>
                <span>{layer.detail}</span>
              </div>
            ))}
          </div>
        </BorderGlow>
      </motion.section>

      <section className="grid two-col">
        <motion.article
          className=""
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.45, delay: 0.05 }}
        >
          <BorderGlow className="panel glass">
            <GradientText className="text-2xl font-bold mb-3" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
              Methodologies
            </GradientText>
            <ol className="bullet-list numbered-list">
              {methodologies.map((method) => (
                <li key={method}>{method}</li>
              ))}
            </ol>
          </BorderGlow>
        </motion.article>

        <motion.article
          className=""
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.45, delay: 0.12 }}
        >
          <BorderGlow className="panel glass">
            <GradientText className="text-2xl font-bold mb-3" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
              Live Pipeline Modes
            </GradientText>
            <div className="team-list">
              <div className="team-card">
                <strong>Fog-Only Mode</strong>
                <span>Optimized fog probability estimation with configurable dehaze behavior.</span>
              </div>
              <div className="team-card">
                <strong>Pothole-Only Mode</strong>
                <span>YOLO-based detection path tuned for realtime frame throughput.</span>
              </div>
              <div className="team-card">
                <strong>Combined Mode</strong>
                <span>Unified inference output for risk fusion and decision support.</span>
              </div>
            </div>
          </BorderGlow>
        </motion.article>
      </section>

      <section className="grid two-col">
        <motion.article
          className=""
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.45, delay: 0.05 }}
        >
          <BorderGlow className="panel glass">
            <GradientText className="text-2xl font-bold mb-3" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
              Team
            </GradientText>
            <div className="team-table-wrap">
              <table className="team-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>USN</th>
                    <th>Branch</th>
                  </tr>
                </thead>
                <tbody>
                  {team.map((member) => (
                    <tr key={member.name}>
                      <td>{member.name}</td>
                      <td>{member.usn}</td>
                      <td>{member.branch}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </BorderGlow>
        </motion.article>

        <motion.article
          className=""
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.45, delay: 0.12 }}
        >
          <BorderGlow className="panel glass">
            <GradientText className="text-2xl font-bold mb-3" colors={['#4b84ff', '#9b59ff', '#5ce1e6']} animationSpeed={8}>
              Tech Stack
            </GradientText>
            <div className="team-list">
              {stackGroups.map((group) => (
                <div key={group.title} className="team-card">
                  <strong>{group.title}</strong>
                  <div className="stack-grid" style={{ marginTop: '8px' }}>
                    {group.items.map((item) => (
                      <span key={item} className="chip">
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </BorderGlow>
        </motion.article>
      </section>
    </div>
  )
}
