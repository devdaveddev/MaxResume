import { useEffect, useMemo, useState } from 'react'
import { ListChecks, SlidersHorizontal, ChevronDown, ChevronUp, RotateCcw, Pencil } from 'lucide-react'
import { Card, Chip, Help, Spinner } from './ui'

const LEVELS = [
  [0, 'No requirement'], [1, 'Diploma / Associate'], [2, "Bachelor's"], [3, "Master's"], [4, 'Doctorate'],
]
const WEIGHT_LABELS = {
  required_skills: 'Required skills',
  experience: 'Relevant experience',
  semantic: 'Semantic fit',
  preferred_skills: 'Preferred & soft skills',
  education: 'Education',
}
const DEFAULT_WEIGHTS = { required_skills: 0.4, experience: 0.2, semantic: 0.2, preferred_skills: 0.1, education: 0.1 }

function SkillEditor({ label, skills, onChange, allSkills, kind, alternatives }) {
  const [draft, setDraft] = useState('')
  const add = () => {
    const name = allSkills.find((s) => s.toLowerCase() === draft.trim().toLowerCase()) || draft.trim()
    if (name && !skills.includes(name)) onChange([...skills, name])
    setDraft('')
  }
  const altOf = (s) => alternatives.find((g) => g.includes(s))
  return (
    <div className="skill-editor">
      <div className="label-row"><strong>{label}</strong><span className="muted">{skills.length}</span></div>
      <div className="chips">
        {skills.map((s) => (
          <Chip key={s} kind={kind} onRemove={() => onChange(skills.filter((x) => x !== s))}
                title={altOf(s) ? `Any of: ${altOf(s).join(' / ')}` : undefined}>
            {s}{altOf(s) ? ' ⇄' : ''}
          </Chip>
        ))}
        <input
          className="chip-input" list="skill-list" value={draft} placeholder="+ add skill"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
          onBlur={() => draft.trim() && add()}
        />
      </div>
    </div>
  )
}


export default function Requirements({ job, allSkills, onSave, defaultOpen = true }) {
  const p = job.parsed
  const [open, setOpen] = useState(defaultOpen)
  useEffect(() => setOpen(defaultOpen), [defaultOpen])
  const [req, setReq] = useState(p.required_skills)
  const [pref, setPref] = useState(p.preferred_skills)
  const [years, setYears] = useState(p.min_years ?? '')
  const [edu, setEdu] = useState(p.education.min_level)
  const [weights, setWeights] = useState(job.weights)
  const [showWeights, setShowWeights] = useState(false)
  const [showText, setShowText] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setReq(p.required_skills); setPref(p.preferred_skills); setYears(p.min_years ?? '')
    setEdu(p.education.min_level); setWeights(job.weights)
  }, [job])

  const dirty = useMemo(() => (
    JSON.stringify(req) !== JSON.stringify(p.required_skills) ||
    JSON.stringify(pref) !== JSON.stringify(p.preferred_skills) ||
    String(years) !== String(p.min_years ?? '') || edu !== p.education.min_level ||
    JSON.stringify(weights) !== JSON.stringify(job.weights)
  ), [req, pref, years, edu, weights, job, p])

  const wSum = Object.values(weights).reduce((a, b) => a + b, 0) || 1

  async function save() {
    setSaving(true)
    try {
      await onSave({
        required_skills: req, preferred_skills: pref,
        min_years: years === '' ? null : Number(years), education_min_level: Number(edu), weights,
      })
    } finally {
      setSaving(false)
    }
  }

  const summaryLine = [
    `${p.required_skills.length} must-have skills`,
    `${p.preferred_skills.length} nice-to-have`,
    p.min_years ? `${p.min_years}+ years` : 'no years requirement',
    p.education.min_level_name || 'no degree requirement',
  ].join(' · ')

  if (!open) {
    return (
      <Card title="What the job needs" icon={<ListChecks size={18} />}
            actions={<button className="btn btn-ghost btn-sm" onClick={() => setOpen(true)}><Pencil size={13} /> Review &amp; edit</button>}>
        <p className="muted req-summary">{summaryLine}</p>
        <div className="chips">
          {p.required_skills.slice(0, 12).map((s) => <Chip key={s} kind="req">{s}</Chip>)}
          {p.required_skills.length > 12 && <Chip>+{p.required_skills.length - 12}</Chip>}
        </div>
      </Card>
    )
  }

  return (
    <Card
      title="What the job needs" icon={<ListChecks size={18} />}
      actions={<>
        <button className="link" onClick={() => setShowText(!showText)}>{showText ? 'Hide' : 'View'} JD text</button>
        {!defaultOpen && <button className="link" onClick={() => setOpen(false)}><ChevronUp size={14} /> Collapse</button>}
      </>}
    >
      <p className="muted small intro-note">
        Extracted automatically from the JD. Fix anything that looks wrong: remove a skill with ×, type to add one,
        and every candidate is re-scored when you save.
      </p>
      {showText && <pre className="jd-text">{job.text}</pre>}

      <SkillEditor label="Must-have skills" skills={req} onChange={setReq} allSkills={allSkills} kind="req" alternatives={p.alternatives || []} />
      <SkillEditor label="Nice-to-have skills" skills={pref} onChange={setPref} allSkills={allSkills} kind="pref" alternatives={p.alternatives || []} />
      {p.soft_skills?.length > 0 && (
        <div className="skill-editor">
          <div className="label-row"><strong>Soft skills</strong><span className="muted">half weight</span></div>
          <div className="chips">{p.soft_skills.map((s) => <Chip key={s}>{s}</Chip>)}</div>
        </div>
      )}

      <div className="req-grid">
        <label className="field">
          <span>Minimum experience (years)</span>
          <input type="number" min="0" max="40" step="0.5" value={years} placeholder="none"
                 onChange={(e) => setYears(e.target.value)} />
          {p.max_years && <small className="muted">JD range: {p.min_years}–{p.max_years} years</small>}
        </label>
        <label className="field">
          <span>Minimum education</span>
          <select value={edu} onChange={(e) => setEdu(Number(e.target.value))}>
            {LEVELS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          {p.education.fields?.length > 0 && (
            <small className="muted">
              Field: {p.education.fields.join(', ')}{p.education.related_fields_ok ? ' or related' : ''}
              {p.education.equivalent_experience_ok ? ' · equivalent experience accepted' : ''}
            </small>
          )}
        </label>
      </div>

      {p.requirements?.length > 0 && (
        <details className="statements">
          <summary>{p.requirements.length} requirement statements used for semantic matching</summary>
          <ul>{p.requirements.map((r) => <li key={r}>{r}</li>)}</ul>
        </details>
      )}

      <button className="link weights-toggle" onClick={() => setShowWeights(!showWeights)}>
        <SlidersHorizontal size={14} /> Adjust scoring weights {showWeights ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      <Help label="What are scoring weights?">
        The match score is a weighted average of five parts. Raise a weight to make that part matter more,
        e.g. increase <em>Relevant experience</em> for senior roles.
      </Help>
      {showWeights && (
        <div className="weights">
          {Object.keys(WEIGHT_LABELS).map((k) => (
            <label key={k} className="weight-row">
              <span>{WEIGHT_LABELS[k]}</span>
              <input type="range" min="0" max="1" step="0.05" value={weights[k]}
                     onChange={(e) => setWeights({ ...weights, [k]: Number(e.target.value) })} />
              <span className="mono">{Math.round((weights[k] / wSum) * 100)}%</span>
            </label>
          ))}
          <p className="muted small">Weights are normalised to 100%. Components the JD does not specify are skipped and the rest re-normalised.</p>
          <button className="link" onClick={() => setWeights(DEFAULT_WEIGHTS)}><RotateCcw size={12} /> Reset defaults</button>
        </div>
      )}

      {dirty && (
        <button className="btn btn-primary save-btn" onClick={save} disabled={saving}>
          {saving ? <Spinner label="Re-scoring candidates…" /> : 'Save changes & re-score'}
        </button>
      )}
    </Card>
  )
}
