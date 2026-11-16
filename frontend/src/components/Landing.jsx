import { FileText, UploadCloud, ScanSearch, Trophy, MessageSquareText, Briefcase, ArrowRight, CheckCircle2, MinusCircle, AlertCircle, ShieldCheck, Lock, Sparkles } from 'lucide-react'
import JobForm from './JobForm'
import { Avatar } from './ui'

const STEPS = [
  { icon: <FileText size={22} />, title: 'Add the job description', text: 'Paste it or upload a file. Must-have skills, years and degree are pulled out for you to review.' },
  { icon: <UploadCloud size={22} />, title: 'Drop in resumes', text: 'Upload 10, 20 or 50 at once: PDF, Word, even scanned copies.' },
  { icon: <ScanSearch size={22} />, title: 'Every resume is read', text: 'Contacts, roles, dates, skills and education become a clean profile, with a confidence check.' },
  { icon: <Trophy size={22} />, title: 'Get a ranked shortlist', text: 'Candidates are scored 0–100 on skills, relevant experience and how well their work fits the role.' },
  { icon: <MessageSquareText size={22} />, title: 'See why', text: 'Open anyone to see matched and missing skills, the evidence, and how the score adds up.' },
]

// Decorative product mock-ups for the hero (illustrative, not live data).
function HeroArt() {
  return (
    <div className="hero-art" aria-hidden="true">
      <div className="glow glow-a" />
      <div className="glow glow-b" />
      <div className="float-card card-jd">
        <p className="fc-title">What does this role need?</p>
        {['Java & Spring Boot', 'Kafka or similar', '5+ years backend', "Bachelor's in CS"].map((t, i) => (
          <label key={t} className="fc-option"><span className={`fc-check ${i < 3 ? 'on' : ''}`} />{t}</label>
        ))}
      </div>
      <div className="float-card card-rank">
        <p className="fc-title">Top matches</p>
        {[['Aarav Mehta', 85], ['Rohan Iyer', 80], ['Lucia Fernandes', 78]].map(([n, s]) => (
          <div key={n} className="fc-row">
            <Avatar name={n} size={26} />
            <span>{n}</span>
            <span className="fc-bar"><span style={{ width: `${s}%` }} /></span>
            <strong>{s}%</strong>
          </div>
        ))}
      </div>
      <div className="float-card card-upload">
        <p className="fc-title center">Add resumes</p>
        <p className="fc-sub">PDF, DOCX or scanned, many at a time</p>
        <span className="fc-btn"><UploadCloud size={13} /> Upload resumes</span>
      </div>
    </div>
  )
}

export default function Landing({ jobs, onCreated, onOpenJob }) {
  const toStart = () => document.getElementById('start')?.scrollIntoView({ behavior: 'smooth' })

  return (
    <div className="landing">
      {/* ---------------- hero ---------------- */}
      <section className="hero">
        <div className="hero-copy">
          <p className="hero-eyebrow"><Sparkles size={18} /> AI hiring assistant</p>
          <h1 className="display">Rank every<br />resume in<br />minutes</h1>
          <p className="hero-lead">
            Give MaxResume a job description and a stack of resumes. It reads each one, compares it with
            what the role really needs, and hands you a ranked shortlist where every score is explained.
          </p>
          <div className="hero-cta">
            <button className="btn btn-ink btn-xl" onClick={toStart}>Start with a job description <ArrowRight size={18} /></button>
          </div>
          <p className="fine">No account needed. Sample job descriptions and synthetic resumes are one click away.</p>
        </div>
        <HeroArt />
      </section>

      {/* ---------------- value strip ---------------- */}
      <section className="value-strip">
        <span>Understands meaning, not just keywords</span>
        <i className="spark" aria-hidden="true" />
        <span><Lock size={16} /> Candidate data stays private</span>
        <i className="spark" aria-hidden="true" />
        <span><ShieldCheck size={16} /> Every action audited</span>
      </section>

      {/* ---------------- how it works ---------------- */}
      <section className="how">
        <h2 className="section-title">How MaxResume works</h2>
        <ol className="how-steps">
          {STEPS.map((s) => (
            <li key={s.title}>
              <span className="how-icon">{s.icon}</span>
              <h3>{s.title}</h3>
              <p>{s.text}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* ---------------- explained panel ---------------- */}
      <section className="explain-panel">
        <p className="panel-kicker">Why MaxResume</p>
        <div className="explain-grid">
          <div className="explain-card">
            <p className="ec-head"><span className="ec-score">67.5%</span> Daniel Okafor · Good match</p>
            <ul>
              <li className="positive"><CheckCircle2 size={15} /> Has 9 of 15 required skills: Java, Spring Boot, PostgreSQL…</li>
              <li className="neutral"><MinusCircle size={15} /> Kafka not named, but implied by “a real-time event streaming platform…” (half credit)</li>
              <li className="neutral"><MinusCircle size={15} /> No AWS, but has GCP, a close substitute</li>
              <li className="positive"><CheckCircle2 size={15} /> 6.5 years relevant experience; role asks for 5+</li>
              <li className="negative"><AlertCircle size={15} /> Missing: JUnit, Agile</li>
            </ul>
            <p className="ec-formula">40%×68 + 20%×100 + 20%×41 + 10%×21 + 10%×100 = 67.5%</p>
          </div>
          <div className="explain-copy">
            <h3>Every score explained</h3>
            <p>
              No black box. Each match shows the skills found and missing, which experience counted and why,
              the resume sentences that back it up, and the exact formula behind the percentage. You stay in
              control: edit the requirements or weights and every candidate is re-scored instantly.
            </p>
          </div>
        </div>
      </section>

      {/* ---------------- start ---------------- */}
      <section className="start-section" id="start">
        <div className="start-copy">
          <h2 className="section-title">Start with the role</h2>
          <p className="muted">Paste a job description or pick a sample to see it in action.</p>
          {jobs.length > 0 && (
            <div className="recent">
              <h3>Continue where you left off</h3>
              <ul>
                {jobs.slice(0, 6).map((j) => (
                  <li key={j.id}>
                    <button className="recent-job" onClick={() => onOpenJob(j.id)}>
                      <Briefcase size={15} /> <span>{j.title}</span>
                      <span className="muted small">{j.candidate_count} candidate{j.candidate_count === 1 ? '' : 's'}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <JobForm onCreated={onCreated} />
      </section>
    </div>
  )
}
