import { useEffect, useRef, useState } from 'react'
import { FileText, Upload, Sparkles, Wand2 } from 'lucide-react'
import { api, samples } from '../api'
import { Card, Spinner } from './ui'
import { useToast } from './toast'

// Module 1: paste or upload a job description.
export default function JobForm({ onCreated }) {
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sampleJds, setSampleJds] = useState([])
  const fileInput = useRef(null)
  const notify = useToast()

  useEffect(() => { samples.list().then((s) => setSampleJds(s.job_descriptions)).catch(() => {}) }, [])

  async function submit(e) {
    e.preventDefault()
    setError('')
    if (!file && text.trim().length < 50) {
      setError('Paste a job description (at least 50 characters) or upload a file.')
      return
    }
    setBusy(true)
    try {
      const job = await api.createJob({ text: file ? null : text, title, file })
      notify(`Found ${job.parsed.required_skills.length} must-have and ${job.parsed.preferred_skills.length} nice-to-have skills`)
      onCreated(job)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Start with the job description" icon={<FileText size={18} />} className="job-form">
      {sampleJds.length > 0 && (
        <div className="sample-row">
          <Wand2 size={14} /> <span>No JD handy? Try a sample:</span>
          {sampleJds.map((s) => (
            <button key={s.name} type="button" className="pill-btn" onClick={() => { setText(s.text); setFile(null); setTitle('') }}>
              {s.name}
            </button>
          ))}
        </div>
      )}
      <form onSubmit={submit}>
        <label className="field">
          <span>Job title <em>(optional, detected automatically)</em></span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Senior Java Backend Engineer" />
        </label>

        <label className="field">
          <span>Paste the job description</span>
          <textarea
            value={text}
            onChange={(e) => { setText(e.target.value); setFile(null) }}
            rows={13}
            placeholder={'Responsibilities\n• Design and build microservices…\n\nRequirements\n• 5+ years of experience…\n\nNice to have\n• Redis…'}
            disabled={!!file}
          />
        </label>

        <div className="or-row">
          <span>or</span>
          <button type="button" className="btn btn-ghost" onClick={() => fileInput.current.click()}>
            <Upload size={16} /> Upload a JD file
          </button>
          <span className="muted small">PDF, DOCX or TXT</span>
          <input
            ref={fileInput} type="file" accept=".pdf,.docx,.txt" hidden
            onChange={(e) => { setFile(e.target.files[0] || null); e.target.value = '' }}
          />
          {file && (
            <span className="file-picked">
              {file.name}
              <button type="button" className="link" onClick={() => setFile(null)}>remove</button>
            </span>
          )}
        </div>

        {error && <p className="error">{error}</p>}

        <button className="btn btn-primary btn-lg" disabled={busy}>
          {busy ? <Spinner label="Reading the job description…" /> : <><Sparkles size={16} /> Extract requirements</>}
        </button>
      </form>
    </Card>
  )
}
