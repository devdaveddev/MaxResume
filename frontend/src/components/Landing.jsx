import { useRef } from 'react'
import { FileText, UploadCloud, Paperclip, X, ScanSearch, Trophy, MessageSquareText, Briefcase, ArrowRight, CheckCircle2, MinusCircle, AlertCircle, ShieldCheck, Lock, Sparkles } from 'lucide-react'
import JobForm from './JobForm'
import { Avatar } from './ui'

const STEPS = [
  { icon: <FileText size={22} />, title: 'Add the job description', text: 'Paste it or upload a file. Must-have skills, years and degree are pulled out for you to review.' },
  { icon: <UploadCloud size={22} />, title: 'Drop in resumes', text: 'Upload 10, 20 or 50 at once: PDF, Word, even scanned copies.' },
  { icon: <ScanSearch size={22} />, title: 'Every resume is read', text: 'Contacts, roles, dates, skills and education become a clean profile, with a confidence check.' },
  { icon: <Trophy size={22} />, title: 'Get a ranked shortlist', text: 'Candidates are scored 0–100 on skills, relevant experience and how well their work fits the role.' },
  { icon: <MessageSquareText size={22} />, title: 'See why', text: 'Open anyone to see matched and missing skills, the evidence, and how the score adds up.' },
]

const RESUME_TYPES = '.pdf,.docx,.doc,.odt,.rtf,.txt'

// Product mock-ups for the hero. The two preview cards are decorative; the upload card is real:
// it opens the file picker, keeps the chosen resumes ready, and they are analysed automatically
// as soon as the job description is added (every score needs a job to compare against).
function HeroArt({ onPick, pendingCount }) {
  const input = useRef(null)
  return (
    <div className="hero-art">
      <div className="glow glow-a" aria-hidden="true" />
      <div className="glow glow-b" aria-hidden="true" />
      <div className="float-card card-jd" aria-hidden="true">
        <p className="fc-title">What does this role need?</p>
        {['Java & Spring Boot', 'Kafka or similar', '5+ years backend', "Bachelor's in CS"].map((t, i) => (
          <label key={t} className="fc-option"><span className={`fc-check ${i < 3 ? 'on' : ''}`} />{t}</label>
        ))}
      </div>
      <div className="float-card card-rank" aria-hidden="true">
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
        <p className="fc-sub">
          {pendingCount ? `${pendingCount} resume${pendingCount > 1 ? 's' : ''} ready to analyse`
            : 'PDF, Word or scanned. Pick as many as you like.'}
        </p>
        <button type="button" className="fc-btn" onClick={() => input.current.click()}>
          <UploadCloud size={13} /> {pendingCount ? 'Change resumes' : 'Upload resumes'}
        </button>
        <input ref={input} type="file" multiple hidden accept={RESUME_TYPES}
               onChange={(e) => { if (e.target.files.length) onPick(Array.from(e.target.files)); e.target.value = '' }} />
      </div>
    </div>
  )
}

export default function Landing({ jobs, onCreated, onOpenJob, pendingResumes, onPickResumes, onClearResumes }) {
  // Scroll to the JD form and put the cursor in it: adding the job is always step 1.
  const toStart = () => {
    document.getElementById('start')?.scrollIntoView({ behavior: 'smooth' })
    setTimeout(() => document.querySelector('.job-form textarea')?.focus({ preventScroll: true }), 500)
  }

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
        <HeroArt pendingCount={pendingResumes.length} onPick={(files) => { onPickResumes(files); toStart() }} />
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
            <p className="ec-head"><span className="ec-score">67.5%</span> Riya Gupta · Good match</p>
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
            <h3>Every score, explained</h3>
            <p>
              You shouldn&apos;t have to trust a number you can&apos;t question. Click on anyone and MaxResume shows its
              working: the skills it found, the ones that are missing, which jobs it counted as relevant, and
              the lines from their resume that back it all up.
            </p>
            <p>
              The percentage comes with its formula, so you can check the maths yourself. And if you disagree
              with a requirement, change it. Every candidate is re-scored on the spot.
            </p>
          </div>
        </div>
      </section>

      {/* ---------------- start ---------------- */}
      <section className="start-section" id="start">
        <div className="start-copy">
          <h2 className="section-title">Start with the role</h2>
          {pendingResumes.length > 0 && (
            <div className="pending-resumes" role="status">
              <Paperclip size={16} />
              <div>
                <strong>{pendingResumes.length} resume{pendingResumes.length > 1 ? 's' : ''} ready.</strong>{' '}
                Add the job description and they&apos;ll be analysed straight away.
                <div className="muted small pending-names">
                  {pendingResumes.slice(0, 4).map((f) => f.name).join(', ')}{pendingResumes.length > 4 ? ` +${pendingResumes.length - 4} more` : ''}
                </div>
              </div>
              <button className="icon-btn" onClick={onClearResumes} aria-label="Remove selected resumes"><X size={14} /></button>
            </div>
          )}
          {pendingResumes.length === 0 && <ol className="start-steps">
            <li><strong>Add the job description.</strong> Paste it, upload it, or pick a sample.</li>
            <li><strong>Upload resumes.</strong> The upload box appears on the next screen, right after the
              requirements are extracted.</li>
          </ol>}
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
        <JobForm onCreated={onCreated} pendingCount={pendingResumes.length} />
      </section>
    </div>
  )
}
