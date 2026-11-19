import { useEffect, useState } from 'react'
import {
  X, Mail, Phone, MapPin, Linkedin, Github, FileDown, Briefcase, GraduationCap, CheckCircle2,
  AlertCircle, MinusCircle, Calculator, MessageSquareText, Sparkles, Award, ChevronLeft, ChevronRight,
  ScanSearch, ShieldCheck,
} from 'lucide-react'
import { api, download } from '../api'
import { useToast } from './toast'
import { Avatar, Chip, Help, ScoreRing, Spinner, Verdict, fmtYears, scoreColor } from './ui'

const REASON_ICON = {
  positive: <CheckCircle2 size={16} className="c-good" />,
  neutral: <MinusCircle size={16} className="c-warn" />,
  negative: <AlertCircle size={16} className="c-bad" />,
}
const TABS = ['Overview', 'Skills', 'Experience', 'Evidence', 'Profile']

function Section({ icon, title, children, aside }) {
  return (
    <section className="panel-section">
      <h3>{icon}{title}{aside && <span className="aside">{aside}</span>}</h3>
      {children}
    </section>
  )
}

function Breakdown({ match }) {
  const applied = match.breakdown.filter((b) => b.applied)
  return (
    <div className="breakdown">
      {match.breakdown.map((b) => (
        <div key={b.key} className={`bd-row ${b.applied ? '' : 'skipped'}`}>
          <div className="bd-label">
            <span>{b.label}</span>
            <span className="muted small">{b.applied ? `worth ${Math.round(b.weight * 100)} pts` : 'not in JD, skipped'}</span>
          </div>
          <div className="bd-bar">
            {b.applied && <div className="bd-fill" style={{ width: `${b.score * 100}%`, background: scoreColor(b.score * 100) }} />}
          </div>
          <div className="bd-pts mono">{b.applied ? `${b.points.toFixed(1)} / ${b.max_points.toFixed(0)}` : '—'}</div>
        </div>
      ))}
      <div className="bd-formula mono small">
        {applied.map((b) => `${Math.round(b.weight * 100)}%×${(b.score * 100).toFixed(0)}`).join(' + ')} = <strong>{match.score.toFixed(1)}%</strong>
      </div>
    </div>
  )
}

function SkillRow({ item, kind }) {
  const [open, setOpen] = useState(false)
  const detail = item.evidence || item.closest_evidence
  let note = ''
  if (kind === 'match') note = item.how
  if (kind === 'partial') note = item.how === 'similar skill' ? `has ${item.via.join(', ')} instead` : `implied by experience (sim ${item.similarity})`
  if (item.satisfied_by) note += ` · via ${item.satisfied_by}`
  return (
    <li className={`skill-row ${detail ? 'clickable' : ''}`} onClick={() => detail && setOpen(!open)}>
      <div className="skill-row-head">
        <Chip kind={kind}>{item.skill}</Chip>
        <span className="muted small">{note}</span>
        {item.credit !== undefined && <span className="credit mono small">{Math.round(item.credit * 100)}%</span>}
      </div>
      {open && detail && <blockquote>{detail}</blockquote>}
    </li>
  )
}

function ExperienceBars({ exp }) {
  const max = Math.max(exp.required_min || 0, exp.candidate_years || 0, exp.required_max || 0, 1) * 1.1
  const bar = (label, val, cls) => (
    <div className="exp-bar">
      <span>{label}</span>
      <div className="exp-track"><div className={`exp-fill ${cls}`} style={{ width: `${((val || 0) / max) * 100}%` }} /></div>
      <span className="mono">{fmtYears(val)}</span>
    </div>
  )
  return (
    <div className="exp-bars">
      {exp.required_min != null && bar(`JD asks${exp.required_max ? ` (${exp.required_min}–${exp.required_max})` : ' (min)'}`, exp.required_min, 'req')}
      {bar('Total', exp.candidate_years, 'total')}
      {bar('Relevant', exp.relevant_years, 'rel')}
      {bar('Effective', exp.effective_years, 'eff')}
      <p className="muted small">Effective = relevant years + ¼ of unrelated years (capped at half the requirement). Result: <strong>{exp.status}</strong></p>
    </div>
  )
}

export default function CandidatePanel({ id, ids, onNavigate, onClose }) {
  const [c, setC] = useState(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('Overview')
  const idx = ids.indexOf(id)
  const prev = idx > 0 ? ids[idx - 1] : null
  const next = idx >= 0 && idx < ids.length - 1 ? ids[idx + 1] : null

  useEffect(() => {
    setC(null); setError('')
    api.candidate(id).then(setC).catch((e) => setError(e.message))
  }, [id])

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowRight' && next) onNavigate(next)
      if (e.key === 'ArrowLeft' && prev) onNavigate(prev)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, onNavigate, next, prev])

  return (
    <div className="overlay" onClick={onClose}>
      <aside className="panel" onClick={(e) => e.stopPropagation()} aria-label="Candidate analysis">
        <div className="panel-nav">
          <span className="muted small">Candidate {idx + 1} of {ids.length}</span>
          <div>
            <button className="btn btn-ghost btn-sm" disabled={!prev} onClick={() => onNavigate(prev)} title="Previous (←)"><ChevronLeft size={14} /> Prev</button>
            <button className="btn btn-ghost btn-sm" disabled={!next} onClick={() => onNavigate(next)} title="Next (→)">Next <ChevronRight size={14} /></button>
            <button className="icon-btn" onClick={onClose} aria-label="Close (Esc)"><X size={18} /></button>
          </div>
        </div>
        {error && <p className="error">{error}</p>}
        {!c && !error && <div className="panel-loading"><Spinner label="Loading analysis…" /></div>}
        {c && <PanelBody c={c} tab={tab} setTab={setTab} />}
      </aside>
    </div>
  )
}

function PanelBody({ c, tab, setTab }) {
  const notify = useToast()
  const p = c.profile
  const m = c.match
  const sk = m.skills
  const exp = m.experience
  const edu = m.education
  const pos = m.reasons.filter((r) => r.kind === 'positive').length
  const neg = m.reasons.filter((r) => r.kind === 'negative').length

  return (
    <>
      <header className="panel-head">
        <div className="panel-id">
          <Avatar name={p.name} size={56} />
          <div>
            <h2>{p.name}</h2>
            <p className="muted">{p.current_title || '—'} · {fmtYears(p.total_years)} experience</p>
            <div className="contact">
              {p.email && <span><Mail size={13} />{p.email}</span>}
              {p.phone && <span><Phone size={13} />{p.phone}</span>}
              {p.location && <span><MapPin size={13} />{p.location}</span>}
              {p.linkedin && <span><Linkedin size={13} />{p.linkedin}</span>}
              {p.github && <span><Github size={13} />{p.github}</span>}
            </div>
          </div>
        </div>
        <div className="panel-score">
          <ScoreRing score={m.score} size={104} />
          <Verdict verdict={m.verdict} score={m.score} />
        </div>
      </header>

      <div className="quick-facts">
        <div><span className="qf-num c-good">{sk.matched.length}</span><span>of {sk.required_count} must-haves</span></div>
        <div><span className="qf-num c-warn">{sk.partial.length}</span><span>partial matches</span></div>
        <div><span className="qf-num c-bad">{sk.missing.length}</span><span>missing skills</span></div>
        <div><span className="qf-num">{fmtYears(exp.relevant_years)}</span><span>relevant experience{exp.required_min ? ` (needs ${exp.required_min}+)` : ''}</span></div>
      </div>

      {c.quality && c.quality.level !== 'high' && (
        <div className={`parse-banner ${c.quality.level}`}>
          <ScanSearch size={16} />
          <div>
            <strong>Parse confidence {c.quality.confidence}% ({c.quality.level}).</strong>{' '}
            {c.quality.issues.slice(0, 2).join(' ')}{' '}
            <button className="link" onClick={() => setTab('Profile')}>See details</button>
          </div>
        </div>
      )}

      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>{t}</button>
        ))}
      </nav>

      {tab === 'Overview' && (
        <>
          <Section icon={<MessageSquareText size={16} />} title="Why this score" aside={`${pos} strengths · ${neg} concerns`}>
            <ul className="reasons">
              {m.reasons.map((r, i) => <li key={i} className={r.kind}>{REASON_ICON[r.kind]}<span>{r.text}</span></li>)}
            </ul>
          </Section>
          <Section icon={<Calculator size={16} />} title="How the score adds up">
            <Breakdown match={m} />
          </Section>
        </>
      )}

      {tab === 'Skills' && (
        <Section icon={<CheckCircle2 size={16} />} title="Skills vs. the job"
                 aside={<Help label="How are skills credited?">
                   <ul>
                     <li><strong>100%</strong>: named and used in work experience</li>
                     <li><strong>85%</strong>: listed only, or implied by a tool (Spring Boot ⇒ Spring)</li>
                     <li><strong>50%</strong>: has a close substitute (MySQL for PostgreSQL) or the experience clearly describes it</li>
                   </ul>
                 </Help>}>
          <div className="skills-grid">
            <div>
              <h4 className="c-good">Has it ({sk.matched.length})</h4>
              <ul className="skill-list">{sk.matched.map((s) => <SkillRow key={s.skill} item={s} kind="match" />)}</ul>
              {sk.matched.length === 0 && <p className="muted small">None</p>}
            </div>
            <div>
              <h4 className="c-warn">Partial credit ({sk.partial.length})</h4>
              <ul className="skill-list">{sk.partial.map((s) => <SkillRow key={s.skill} item={s} kind="partial" />)}</ul>
              {sk.partial.length === 0 && <p className="muted small">None</p>}
              <h4 className="c-bad">Missing ({sk.missing.length})</h4>
              <ul className="skill-list">{sk.missing.map((s) => <SkillRow key={s.skill} item={s} kind="miss" />)}</ul>
              {sk.missing.length === 0 && <p className="muted small">Nothing missing 🎉</p>}
            </div>
          </div>
          {(sk.preferred_matched.length + sk.preferred_partial.length + sk.preferred_missing.length) > 0 && (
            <div className="pref-skills">
              <h4>Nice-to-have</h4>
              <div className="chips">
                {sk.preferred_matched.map((s) => <Chip key={s.skill} kind="match">✓ {s.skill}</Chip>)}
                {sk.preferred_partial.map((s) => <Chip key={s.skill} kind="partial" title={s.evidence}>~ {s.skill}</Chip>)}
                {sk.preferred_missing.map((s) => <Chip key={s.skill} kind="miss">{s.skill}</Chip>)}
              </div>
            </div>
          )}
          {sk.additional.length > 0 && (
            <div className="pref-skills">
              <h4>Other skills on the resume</h4>
              <div className="chips">{sk.additional.map((s) => <Chip key={s}>{s}</Chip>)}</div>
            </div>
          )}
          <p className="muted small hint">Tip: click a skill to see the line of the resume it came from.</p>
        </Section>
      )}

      {tab === 'Experience' && (
        <>
          <Section icon={<Briefcase size={16} />} title="Experience vs. the requirement">
            <ExperienceBars exp={exp} />
            <ul className="roles">
              {exp.roles.map((r, i) => (
                <li key={i} className={r.relevant ? 'relevant' : 'unrelated'}>
                  <div className="role-head">
                    <strong>{r.title}</strong>{r.company && <span className="muted"> · {r.company}</span>}
                    <span className={`badge ${r.relevant ? 'b-good' : 'b-muted'}`}>{r.relevant ? 'Relevant' : 'Unrelated'}</span>
                  </div>
                  <div className="muted small">
                    {r.start.slice(0, 7)} → {r.is_current ? 'present' : r.end.slice(0, 7)} · {fmtYears(Math.round(r.months / 1.2) / 10)} · {r.why}
                  </div>
                </li>
              ))}
              {exp.roles.length === 0 && <p className="muted small">No dated roles found; using the years stated in the resume.</p>}
            </ul>
          </Section>
          <Section icon={<GraduationCap size={16} />} title="Education">
            <ul className="edu">
              {p.education.map((e, i) => (
                <li key={i}><strong>{e.degree}</strong>{e.institution && <> · {e.institution}</>}{e.year && <span className="muted"> · {e.year}</span>}</li>
              ))}
              {p.education.length === 0 && <li className="muted">No degree detected</li>}
            </ul>
            {edu.score != null && (
              <p className="small">
                JD asks for <strong>{edu.required_level || 'a degree'}</strong>
                {edu.required_fields?.length > 0 && <> in {edu.required_fields.join(', ')}{edu.related_fields_ok ? ' or related' : ''}</>}
                {' → '}<strong>{edu.status}</strong>{edu.field_match === false && ', different field'}
              </p>
            )}
          </Section>
        </>
      )}

      {tab === 'Evidence' && (
        <Section icon={<Sparkles size={16} />} title="Semantic evidence" aside={m.semantic.score != null ? `overall fit ${(m.semantic.score * 100).toFixed(0)}%` : ''}>
          <p className="muted small">
            The AI model compares the meaning of each JD requirement with every sentence in the resume,
            so matches count even when the wording differs. These are the closest pairs.
          </p>
          <ul className="evidence">
            {m.semantic.top_matches.map((pair, i) => (
              <li key={i}>
                <div className="ev-req"><span className="tag">JD</span>{pair.requirement}</div>
                <div className="ev-res"><span className="tag">Resume</span>{pair.evidence}</div>
                <div className="ev-sim small">
                  <div className="ev-meter"><div style={{ width: `${pair.coverage * 100}%`, background: scoreColor(pair.coverage * 100) }} /></div>
                  <span className="mono">{pair.similarity.toFixed(2)}</span>
                </div>
              </li>
            ))}
          </ul>
          {m.semantic.gaps.length > 0 && (
            <>
              <h4 className="c-bad">Requirements with little evidence</h4>
              <ul className="gaps">{m.semantic.gaps.map((g, i) => <li key={i}>{g.requirement}</li>)}</ul>
            </>
          )}
        </Section>
      )}

      {tab === 'Profile' && (
        <>
          <Section icon={<Award size={16} />} title="Extracted from the resume"
                   aside={<button className="btn btn-ghost btn-sm" onClick={() => download(api.fileUrl(c.id), { open: true }).catch((e) => notify(e.message, 'error'))}>
                     <FileDown size={14} /> Open original {c.file_type.toUpperCase()}</button>}>
            {p.summary && <p className="summary">“{p.summary}”</p>}
            <dl className="facts">
              <dt>Name</dt><dd>{p.name}{p.field_sources?.name && p.field_sources.name !== 'header' && <span className="muted small"> (from {p.field_sources.name})</span>}</dd>
              <dt>Email</dt><dd>{(p.emails?.length ? p.emails : [p.email]).filter(Boolean).join(', ') || '—'}</dd>
              <dt>Phone</dt><dd>{p.phone || '—'}{p.phone_e164 && p.phone !== p.phone_e164 && <span className="muted small mono"> {p.phone_e164}</span>}</dd>
              <dt>Location</dt><dd>{p.location || '—'}</dd>
              {p.linkedin && <><dt>LinkedIn</dt><dd className="break">{p.linkedin}</dd></>}
              {p.github && <><dt>GitHub</dt><dd className="break">{p.github}</dd></>}
              {p.portfolio?.length > 0 && <><dt>Other links</dt><dd className="break">{p.portfolio.join(', ')}</dd></>}
              <dt>Total experience</dt><dd>{fmtYears(p.total_years)}{p.claimed_years ? ` (resume says ${p.claimed_years}+)` : ''}</dd>
              {p.employment_gaps?.length > 0 && <><dt>Career gaps</dt><dd>{p.employment_gaps.map((g) => `${g.from.slice(0, 7)} → ${g.to.slice(0, 7)} (${g.months} mo)`).join('; ')}</dd></>}
              {p.overlap_months > 0 && <><dt>Overlapping roles</dt><dd>{p.overlap_months} months (counted once)</dd></>}
              <dt>Highest degree</dt><dd>{p.highest_degree || '—'}{p.education?.[0]?.gpa && ` · GPA ${p.education[0].gpa}`}</dd>
              <dt>Skills found</dt><dd>{p.technical_skills.length} technical, {p.soft_skills.length} soft</dd>
              {p.certifications.length > 0 && <><dt>Certifications</dt><dd>{p.certifications.join('; ')}</dd></>}
              <dt>Sections</dt><dd>{p.sections_found.join(', ') || '—'}</dd>
            </dl>
          </Section>

          {c.quality && (
            <Section icon={<ShieldCheck size={16} />} title="How this resume was read"
                     aside={<span className={`conf-pill ${c.quality.level}`}>{c.quality.confidence}% · {c.quality.level} confidence</span>}>
              <ul className="checks">
                {c.quality.checks.map((ch) => (
                  <li key={ch.id} className={ch.status}>
                    {ch.status === 'pass' ? <CheckCircle2 size={15} className="c-good" />
                      : ch.status === 'warn' ? <MinusCircle size={15} className="c-warn" /> : <AlertCircle size={15} className="c-bad" />}
                    <span>{ch.message}</span>
                  </li>
                ))}
              </ul>
              {p.parse_notes?.length > 0 && (
                <ul className="gaps small">{p.parse_notes.map((n) => <li key={n}>{n}</li>)}</ul>
              )}
              {c.extraction && (
                <dl className="facts small extraction">
                  <dt>File</dt><dd>{c.filename} · {c.extraction.file_type.toUpperCase()} · {(c.extraction.size_bytes / 1024).toFixed(0)} KB</dd>
                  <dt>Method</dt><dd className="mono">{c.extraction.method}</dd>
                  {c.extraction.pages && <><dt>Pages</dt><dd>{c.extraction.pages_processed} of {c.extraction.pages} read</dd></>}
                  {c.extraction.ocr_pages?.length > 0 && <><dt>OCR pages</dt><dd>{c.extraction.ocr_pages.join(', ')}</dd></>}
                  {c.extraction.multi_column_pages?.length > 0 && <><dt>Two-column pages</dt><dd>{c.extraction.multi_column_pages.join(', ')}</dd></>}
                  <dt>SHA-256</dt><dd className="mono break" title="Fingerprint of the uploaded file (used for duplicate detection and the audit log)">{c.extraction.sha256.slice(0, 16)}…</dd>
                  {m.meta && <><dt>Scored with</dt><dd className="mono">scorer {m.meta.scorer_version} · {m.meta.embedding_model.split('/').pop()}</dd></>}
                </dl>
              )}
              <details className="raw-wrap">
                <summary>Show the raw text we extracted</summary>
                <pre className="raw">{c.raw_text}</pre>
              </details>
            </Section>
          )}
        </>
      )}
    </>
  )
}
