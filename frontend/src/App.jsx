import { useCallback, useEffect, useMemo, useState } from 'react'
import { Plus, Database, Trash2, History } from 'lucide-react'
import { api } from './api'
import Landing from './components/Landing'
import Requirements from './components/Requirements'
import Uploader from './components/Uploader'
import RankingTable from './components/RankingTable'
import CandidatePanel from './components/CandidatePanel'
import AuditPanel from './components/AuditPanel'
import { Stepper, StatCard, scoreColor } from './components/ui'
import { useToast } from './components/toast'

// The current job id lives in the URL hash (#/job/<id>) so a refresh keeps your place.
const jobIdFromHash = () => (window.location.hash.match(/^#\/job\/(\w+)/) || [])[1] || null

export default function App() {
  const [health, setHealth] = useState(null)
  const [jobs, setJobs] = useState([])
  const [jobId, setJobId] = useState(jobIdFromHash)
  const [job, setJob] = useState(null)
  const [rows, setRows] = useState([])
  const [selected, setSelected] = useState(null)
  const [allSkills, setAllSkills] = useState([])
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [showAudit, setShowAudit] = useState(false)
  const notify = useToast()

  const refreshJobs = useCallback(() => api.listJobs().then(setJobs).catch(() => {}), [])

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ status: 'down' }))
    api.skills().then((s) => setAllSkills(s.map((x) => x.name))).catch(() => {})
    refreshJobs()
    const onHash = () => setJobId(jobIdFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [refreshJobs])

  const loadRows = useCallback((id) => api.candidates(id).then(setRows), [])

  useEffect(() => {
    setJob(null); setRows([]); setSelected(null); setConfirmDelete(false)
    if (!jobId) return
    api.getJob(jobId).then(setJob).catch((e) => { notify(e.message, 'error'); window.location.hash = '' })
    loadRows(jobId).catch(() => {})
  }, [jobId, loadRows, notify])

  const openJob = (id) => { window.location.hash = id ? `#/job/${id}` : '' }

  async function saveRequirements(edits) {
    try {
      const updated = await api.updateJob(job.id, edits)
      setJob(updated)
      await loadRows(job.id)
      notify(rows.length ? `Requirements saved, ${rows.length} candidates re-scored` : 'Requirements saved')
    } catch (e) {
      notify(e.requestId ? `${e.message} (request ${e.requestId})` : e.message, 'error')
    }
  }

  async function deleteJob() {
    if (!confirmDelete) { setConfirmDelete(true); setTimeout(() => setConfirmDelete(false), 3000); return }
    await api.deleteJob(job.id)
    notify(`Deleted “${job.title}”`)
    await refreshJobs()
    openJob(null)
  }

  async function deleteCandidate(row) {
    await api.deleteCandidate(row.id)
    if (selected === row.id) setSelected(null)
    notify(`Removed ${row.name}`)
    await loadRows(job.id)
    refreshJobs()
  }

  const stats = useMemo(() => {
    if (!rows.length) return null
    const avg = rows.reduce((a, r) => a + r.score, 0) / rows.length
    const strong = rows.filter((r) => r.score >= 65).length
    return { avg, strong, top: rows[0] }
  }, [rows])

  const steps = [
    { label: 'Job description', hint: job ? 'requirements extracted' : 'paste or upload', state: job ? 'done' : 'current' },
    { label: 'Upload resumes', hint: rows.length ? `${rows.length} analysed` : 'PDF or DOCX, in bulk', state: !job ? 'todo' : rows.length ? 'done' : 'current' },
    { label: 'Review ranking', hint: 'scores with reasons', state: rows.length ? 'current' : 'todo' },
  ]

  return (
    <div className="app">
      <header className="topbar">
        <a className="brand" href="#" onClick={() => openJob(null)}>
          <span className="logo">M</span> MaxResume <span className="tagline">AI resume matching &amp; ranking</span>
        </a>
        <div className="topbar-right">
          {jobs.length > 0 && (
            <select className="job-select" value={jobId || ''} onChange={(e) => openJob(e.target.value || null)} aria-label="Switch job">
              <option value="">Switch job…</option>
              {jobs.map((j) => <option key={j.id} value={j.id}>{j.title} ({j.candidate_count})</option>)}
            </select>
          )}
          <button className="btn btn-primary btn-sm" onClick={() => openJob(null)}><Plus size={14} /> New job</button>
          {health && (
            <span className={`health ${health.status === 'ok' ? 'up' : 'down'}`}
                  title={health.status === 'ok' ? `Storage: ${health.storage} · Model: ${health.embedding_model}` : 'Backend not reachable'}>
              <Database size={12} /> {health.status === 'ok' ? 'Connected' : 'API offline'}
            </span>
          )}
        </div>
      </header>

      <main className={jobId ? '' : 'main-landing'}>
        {jobId && <Stepper steps={steps} />}

        {!jobId && (
          <Landing jobs={jobs} onOpenJob={openJob} onCreated={(j) => { refreshJobs(); openJob(j.id) }} />
        )}

        {jobId && !job && <div className="loading-page"><span className="spinner" /> Loading job…</div>}

        {job && (
          <>
            <div className="job-title-row">
              <div>
                <span className="eyebrow">Open role</span>
                <h1>{job.title}</h1>
              </div>
              <div className="title-actions">
                <button className="btn btn-ghost btn-sm" onClick={() => setShowAudit(true)}><History size={14} /> Activity log</button>
                <button className={`btn btn-ghost btn-sm danger ${confirmDelete ? 'confirming' : ''}`} onClick={deleteJob}>
                  <Trash2 size={14} /> {confirmDelete ? 'Click again to delete' : 'Delete job'}
                </button>
              </div>
            </div>

            {stats && (
              <div className="stats">
                <StatCard label="Candidates" value={rows.length} sub="analysed for this role" />
                <StatCard label="Good or strong matches" value={stats.strong} sub="scoring 65% or more" accent="var(--good)" />
                <StatCard label="Average match" value={`${stats.avg.toFixed(0)}%`} sub="across all candidates" />
                <button className="stat stat-top" onClick={() => setSelected(stats.top.id)}>
                  <span className="stat-label">Top candidate</span>
                  <span className="stat-value small-value">{stats.top.name}</span>
                  <span className="stat-sub" style={{ color: scoreColor(stats.top.score) }}>{stats.top.score.toFixed(1)}% · view analysis →</span>
                </button>
              </div>
            )}

            <div className={`grid-2 ${rows.length ? 'has-results' : ''}`}>
              <Requirements job={job} allSkills={allSkills} onSave={saveRequirements} defaultOpen={rows.length === 0} />
              <Uploader jobId={job.id} compact={rows.length > 0} highlight={rows.length === 0} onUploaded={() => { loadRows(job.id); refreshJobs() }} />
            </div>
            <RankingTable jobId={job.id} rows={rows} selectedId={selected} onSelect={setSelected} onDelete={deleteCandidate} />
          </>
        )}
      </main>

      {showAudit && job && <AuditPanel jobId={job.id} onClose={() => setShowAudit(false)} />}
      {selected && (
        <CandidatePanel id={selected} ids={rows.map((r) => r.id)} onNavigate={setSelected} onClose={() => setSelected(null)} />
      )}
      <datalist id="skill-list">{allSkills.map((s) => <option key={s} value={s} />)}</datalist>
    </div>
  )
}
