import { useCallback, useEffect, useState } from 'react'
import { X, History, ShieldCheck, ShieldAlert, RefreshCw } from 'lucide-react'
import { api } from '../api'
import { Spinner } from './ui'

const ACTION_LABEL = {
  'job.created': 'Created job',
  'job.updated': 'Edited requirements',
  'job.deleted': 'Deleted job',
  'resume.ingested': 'Added resume',
  'resume.rejected': 'Rejected file',
  'candidate.viewed': 'Viewed candidate',
  'candidate.file_downloaded': 'Opened original file',
  'candidate.deleted': 'Removed candidate',
  'ranking.exported': 'Exported ranking',
  'audit.verified': 'Verified audit log',
}

function describe(e) {
  const d = e.details || {}
  switch (e.action) {
    case 'job.created':
      return `${d.required_skills} must-have, ${d.preferred_skills} nice-to-have skills (from ${d.source})`
    case 'job.updated': {
      const parts = Object.entries(d.changes || {}).map(([k, v]) => (
        v.added || v.removed
          ? `${k.replace('_', ' ')}: ${[...(v.added || []).map((x) => `+${x}`), ...(v.removed || []).map((x) => `−${x}`)].join(' ')}`
          : `${k.replace('_', ' ')}: ${JSON.stringify(v.from)} → ${JSON.stringify(v.to)}`
      ))
      return `${parts.join('; ') || 'no changes'} · ${d.rescored} re-scored`
    }
    case 'resume.ingested':
      return `${d.filename} · ${d.score}% · parsed via ${d.extraction_method} (${d.parse_confidence}% confidence)`
    case 'resume.rejected':
      return `${d.filename}: ${d.reason}`
    case 'candidate.deleted':
      return d.filename
    case 'ranking.exported':
      return `${d.rows} rows as ${d.format?.toUpperCase()}`
    case 'audit.verified':
      return `${d.entries} entries, ${d.ok ? 'chain intact' : `BROKEN at #${d.broken_at_seq}`}`
    default:
      return e.target_id ? `${e.target_type} ${e.target_id.slice(0, 8)}` : ''
  }
}

export default function AuditPanel({ jobId, onClose }) {
  const [entries, setEntries] = useState(null)
  const [hideViews, setHideViews] = useState(true)
  const [verify, setVerify] = useState(null)
  const [verifying, setVerifying] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    api.audit({ job_id: jobId, limit: 300 }).then(setEntries).catch((e) => setError(e.message))
  }, [jobId])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function runVerify() {
    setVerifying(true)
    try {
      setVerify(await api.verifyAudit())
      load()
    } catch (e) {
      setError(e.message)
    } finally {
      setVerifying(false)
    }
  }

  const shown = (entries || []).filter((e) => !(hideViews && e.action === 'candidate.viewed'))

  return (
    <div className="overlay" onClick={onClose}>
      <aside className="panel audit" onClick={(e) => e.stopPropagation()} aria-label="Activity log">
        <div className="panel-nav">
          <h2 className="audit-title"><History size={18} /> Activity log</h2>
          <div>
            <button className="btn btn-ghost btn-sm" onClick={load} title="Refresh"><RefreshCw size={14} /></button>
            <button className="icon-btn" onClick={onClose} aria-label="Close (Esc)"><X size={18} /></button>
          </div>
        </div>
        <p className="muted small">
          Every action on this job is recorded with who did it and when. Entries are hash-chained, so editing or
          deleting any past entry is detectable.
        </p>

        <div className="verify-row">
          <button className="btn btn-primary btn-sm" onClick={runVerify} disabled={verifying}>
            {verifying ? <Spinner label="Verifying…" /> : <><ShieldCheck size={14} /> Verify integrity</>}
          </button>
          {verify && (verify.ok
            ? <span className="ok small"><ShieldCheck size={14} /> Chain intact: {verify.entries} entries checked</span>
            : <span className="error small"><ShieldAlert size={14} /> Tampering detected at entry #{verify.broken_at_seq}: {verify.reason}</span>)}
          <label className="small muted toggle">
            <input type="checkbox" checked={hideViews} onChange={(e) => setHideViews(e.target.checked)} /> Hide profile views
          </label>
        </div>

        {error && <p className="error">{error}</p>}
        {!entries && !error && <div className="panel-loading"><Spinner label="Loading activity…" /></div>}
        {entries && (
          <ol className="timeline">
            {shown.map((e) => (
              <li key={e.seq} className={e.outcome !== 'success' ? 'rejected' : ''}>
                <div className="tl-head">
                  <strong>{ACTION_LABEL[e.action] || e.action}</strong>
                  <span className="muted small">{new Date(e.ts).toLocaleString()}</span>
                </div>
                <div className="small">{describe(e)}</div>
                <div className="muted tiny mono">#{e.seq} · {e.actor} · req {e.request_id} · {e.hash.slice(0, 12)}</div>
              </li>
            ))}
            {shown.length === 0 && <p className="muted">No activity yet.</p>}
          </ol>
        )}
      </aside>
    </div>
  )
}
