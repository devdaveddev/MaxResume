import { useEffect, useRef, useState } from 'react'
import { FileText, UploadCloud, Sparkles, Wand2, X } from 'lucide-react'
import { api, samples } from '../api'
import { Card, Spinner } from './ui'
import { useToast } from './toast'

// Module 1: paste or upload a job description.
export default function JobForm({ onCreated, pendingCount = 0 }) {
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sampleJds, setSampleJds] = useState([])
  const [drag, setDrag] = useState(false)
  const fileInput = useRef(null)
  const dragDepth = useRef(0) // dragenter/leave fire for every child element; count them so the highlight doesn't flicker
  const notify = useToast()

  const JD_TYPES = ['pdf', 'docx', 'txt']
  function pickFile(f) {
    if (!f) return
    const ext = f.name.split('.').pop().toLowerCase()
    if (!JD_TYPES.includes(ext)) { setError(`“${f.name}” isn't a PDF, DOCX or TXT file.`); return }
    setError(''); setFile(f)
  }

  // Drops anywhere on the card are caught, so a file dropped on the textarea doesn't open in the browser tab.
  const dropHandlers = {
    onDragEnter: (e) => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); dragDepth.current += 1; setDrag(true) } },
    onDragOver: (e) => { if (e.dataTransfer.types.includes('Files')) e.preventDefault() },
    onDragLeave: () => { dragDepth.current = Math.max(0, dragDepth.current - 1); if (!dragDepth.current) setDrag(false) },
    onDrop: (e) => {
      if (!e.dataTransfer.files.length) return
      e.preventDefault(); dragDepth.current = 0; setDrag(false)
      if (e.dataTransfer.files.length > 1) notify('One job description at a time, so the first file was used', 'error')
      pickFile(e.dataTransfer.files[0])
    },
  }

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
    <Card title="Start with the job description" icon={<FileText size={18} />} className="job-form"
          actions={<span className="step-note">{pendingCount ? `Step 1 of 2 · ${pendingCount} resume${pendingCount > 1 ? 's' : ''} waiting` : 'Step 1 of 2 · next: upload resumes'}</span>}>
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
      <form onSubmit={submit} {...dropHandlers} className={drag ? 'jd-dragging' : ''}>
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

        <div className="or-divider"><span>or upload a file</span></div>
        {file ? (
          <div className="jd-file">
            <FileText size={18} />
            <span className="fname">{file.name}</span>
            <span className="muted small">{file.size < 1024 ? "<1" : (file.size / 1024).toFixed(0)} KB</span>
            <button type="button" className="icon-btn" onClick={() => setFile(null)} aria-label="Remove file"><X size={16} /></button>
          </div>
        ) : (
          <div className={`dropzone compact ${drag ? 'drag' : ''}`} role="button" tabIndex={0}
               onClick={() => fileInput.current.click()}
               onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), fileInput.current.click())}>
            <UploadCloud size={22} />
            <p><strong>Drag &amp; drop a JD file here</strong> or <span className="linkish">browse files</span></p>
            <p className="muted small">PDF, DOCX or TXT</p>
          </div>
        )}
        <input
          ref={fileInput} type="file" accept=".pdf,.docx,.txt" hidden
          onChange={(e) => { pickFile(e.target.files[0]); e.target.value = '' }}
        />

        {error && <p className="error">{error}</p>}

        <button className="btn btn-primary btn-lg" disabled={busy}>
          {busy ? <Spinner label="Reading the job description…" /> : <><Sparkles size={16} /> {pendingCount ? `Extract requirements & analyse ${pendingCount} resume${pendingCount > 1 ? 's' : ''}` : 'Extract requirements'}</>}
        </button>
      </form>
    </Card>
  )
}
