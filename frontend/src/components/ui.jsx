
export function scoreColor(score) {
  if (score >= 80) return 'var(--good)'
  if (score >= 65) return 'var(--ok)'
  if (score >= 50) return 'var(--warn)'
  return 'var(--bad)'
}

export function ScoreRing({ score, size = 96, stroke = 9 }) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const pct = Math.max(0, Math.min(100, score)) / 100
  return (
    <svg width={size} height={size} className="score-ring" role="img" aria-label={`Match score ${score}%`}>
      <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--track)" strokeWidth={stroke} fill="none" />
      <circle
        cx={size / 2} cy={size / 2} r={r} stroke={scoreColor(score)} strokeWidth={stroke} fill="none"
        strokeDasharray={`${c * pct} ${c}`} strokeLinecap="round" transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" fontSize={size * 0.26} fontWeight="700" fill="var(--text)">
        {score.toFixed(score >= 99.95 ? 0 : 1)}
      </text>
    </svg>
  )
}

export function ScoreBar({ score }) {
  return (
    <div className="score-bar">
      <div className="score-bar-track">
        <div className="score-bar-fill" style={{ width: `${score}%`, background: scoreColor(score) }} />
      </div>
      <span className="score-bar-num">{score.toFixed(1)}%</span>
    </div>
  )
}

export function Verdict({ verdict, score }) {
  return <span className="verdict" style={{ color: scoreColor(score), borderColor: scoreColor(score) }}>{verdict}</span>
}

export function Chip({ children, kind = 'neutral', title, onRemove }) {
  return (
    <span className={`chip chip-${kind}`} title={title}>
      {children}
      {onRemove && (
        <button type="button" className="chip-x" onClick={onRemove} aria-label={`Remove ${children}`}>×</button>
      )}
    </span>
  )
}

export function Card({ title, icon, actions, children, className = '' }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          <h2>{icon}{title}</h2>
          <div className="card-actions">{actions}</div>
        </header>
      )}
      {children}
    </section>
  )
}

export function Spinner({ label }) {
  return <span className="spinner-wrap"><span className="spinner" />{label}</span>
}

export const fmtYears = (y) => (y == null ? '—' : `${Number(y).toFixed(1).replace(/\.0$/, '')} yr${y === 1 ? '' : 's'}`)


export function Avatar({ name, size = 34 }) {
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('')
  const hue = [...name].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) % 360, 7)
  return (
    <span className="avatar" style={{ width: size, height: size, fontSize: size * 0.38, background: `hsl(${hue} 65% 92%)`, color: `hsl(${hue} 55% 32%)` }}>
      {initials}
    </span>
  )
}

export function Stepper({ steps }) {
  return (
    <ol className="stepper">
      {steps.map((s, i) => (
        <li key={s.label} className={s.state}>
          <span className="step-dot">{s.state === 'done' ? '✓' : i + 1}</span>
          <span className="step-text"><strong>{s.label}</strong>{s.hint && <small>{s.hint}</small>}</span>
        </li>
      ))}
    </ol>
  )
}

export function StatCard({ label, value, sub, accent }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value" style={accent ? { color: accent } : undefined}>{value}</span>
      {sub && <span className="stat-sub">{sub}</span>}
    </div>
  )
}


export function Help({ children, label = 'How does this work?' }) {
  return (
    <details className="help" onClick={(e) => e.stopPropagation()}>
      <summary aria-label={label} title={label}>?</summary>
      <div className="help-pop">{children}</div>
    </details>
  )
}
