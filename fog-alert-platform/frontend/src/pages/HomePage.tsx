const objectives = [
  'Predict fog intensity in advance to reduce accident risk.',
  'Detect potholes, traffic signs, and road humps from front camera feeds.',
  'Provide real-time hazard alerts with actionable road safety recommendations.',
  'Fuse AI outputs into a single risk score for smarter road monitoring.',
]

const team = [
  { name: 'Member 1', role: 'AIML - Fog & Detection Models' },
  { name: 'Member 2', role: 'AIML - Data & Training Pipeline' },
  { name: 'Member 3', role: 'EC - Embedded Systems & Integration' },
  { name: 'Member 4', role: 'EC - Sensing & Communication' },
]

const stack = ['🐍 Python', '⚛️ React', '🎯 YOLOv8', '🌫️ XGBoost', '📷 OpenCV']

export function HomePage() {
  return (
    <div className="page">
      <section className="hero-section glass">
        <p className="tagline">Predict • Detect • Prevent</p>
        <h1>AEGIS-RS</h1>
        <h2>AI-Based Intelligent Multi-Hazard Road Monitoring System</h2>
      </section>

      <section className="grid two-col">
        <article className="panel glass">
          <h3>About the Project</h3>
          <p>
            AEGIS-RS is a safety-first intelligent road monitoring platform that focuses on fog prediction and
            multi-hazard detection using front-camera vision. It unifies model outputs for fog, potholes, road humps,
            and traffic signs into practical alerts that help prevent high-risk incidents.
          </p>
        </article>

        <article className="panel glass">
          <h3>Objectives</h3>
          <ul className="bullet-list">
            {objectives.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      </section>

      <section className="panel glass">
        <h3>System Overview</h3>
        <div className="flow">
          <div className="flow-node">Front Camera Feed</div>
          <div className="flow-arrow">→</div>
          <div className="flow-node">YOLOv8 + Fog Feature Extraction</div>
          <div className="flow-arrow">→</div>
          <div className="flow-node">XGBoost Fog Prediction</div>
          <div className="flow-arrow">→</div>
          <div className="flow-node">Risk Engine + Alert System</div>
        </div>
      </section>

      <section className="grid two-col">
        <article className="panel glass">
          <h3>Team</h3>
          <div className="team-list">
            {team.map((member) => (
              <div key={member.name} className="team-card">
                <strong>{member.name}</strong>
                <span>{member.role}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="panel glass">
          <h3>Tech Stack</h3>
          <div className="stack-grid">
            {stack.map((item) => (
              <span key={item} className="chip">
                {item}
              </span>
            ))}
          </div>
        </article>
      </section>
    </div>
  )
}
