import { useRef, useState } from 'react'
import { UploadCloud, FileText, X, AlertTriangle, Wand2, CheckCircle2 } from 'lucide-react'
import { api, samples } from '../api'
import { Card, Spinner } from './ui'
import { useToast } from './toast'

const OK_EXT = /\.(pdf|docx|doc|odt|rtf|txt)$/i

// Module 2: batch upload of resumes (PDF / DOCX), drag & drop or file picker.
export default function Uploader({ jobId, onUploaded, compact }) {
  const [files, setFiles] = useState([])
  const [busy, setBusy] = useState(false)
  const [loadingSamples, setLoadingSamples] = useState(false)
  const [drag, setDrag] = useState(false)
  const [result, setResult] = useState(null)
  const input = useRef(null)
  const notify = useToast()

  function addFiles(list) {
    const incoming = Array.from(list)
    setFiles((prev) => {
      const names = new Set(prev.map((f) => f.name))
      return [...prev, ...incoming.filter((f) => !names.has(f.name))]
    })
    setResult(null)
  }

  async function addSamples(group = 'resumes') {
    setLoadingSamples(true)
    try {
      const list = await samples.list()
      addFiles(await samples.resumeFiles(list[group] || [], group))
    } catch (err) {
      notify(`Could not load samples: ${err.message}`, 'error')
    } finally {
      setLoadingSamples(false)
    }
  }

  async function upload() {
    setBusy(true)
    setResult(null)
    try {
      const res = await api.uploadResumes(jobId, files)
      setResult(res)
      setFiles([])
      onUploaded(res)
      if (res.added.length) notify(`${res.added.length} candidate${res.added.length > 1 ? 's' : ''} analysed and ranked`)
      if (res.errors.length) notify(`${res.errors.length} file(s) could not be processed`, 'error')
    } catch (err) {
      setResult({ added: [], errors: [{ filename: 'Upload', error: err.message }] })
    } finally {
      setBusy(false)
    }
  }

  const invalid = files.filter((f) => !OK_EXT.test(f.name))

  return (
    <Card title={compact ? 'Add more resumes' : 'Upload resumes'} icon={<UploadCloud size={18} />}
          actions={!busy && (
            <div className="sample-btns">
              <button className="pill-btn" onClick={() => addSamples('resumes')} disabled={loadingSamples}>
                {loadingSamples ? <Spinner label="Loading…" /> : <><Wand2 size={13} /> Add sample resumes</>}
              </button>
              {!loadingSamples && (
                <button className="pill-btn subtle" onClick={() => addSamples('edge_cases')}
                        title="Scanned PDF, two-column layout, .doc/.rtf/.odt, password-protected and broken files">
                  Try tricky files
                </button>
              )}
            </div>
          )}>
      <div
        className={`dropzone ${drag ? 'drag' : ''} ${compact ? 'compact' : ''}`}
        onClick={() => input.current.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); addFiles(e.dataTransfer.files) }}
        role="button" tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && input.current.click()}
      >
        <UploadCloud size={compact ? 22 : 30} />
        <p><strong>Drag &amp; drop resumes here</strong> or <span className="linkish">browse files</span></p>
        <p className="muted small">PDF, DOCX, DOC, ODT, RTF or TXT · select many at once (up to 50, max 10 MB each) · scanned PDFs are read with OCR</p>
        <input ref={input} type="file" multiple accept=".pdf,.docx,.doc,.odt,.rtf,.txt" hidden
               onChange={(e) => { addFiles(e.target.files); e.target.value = '' }} />
      </div>

      {files.length > 0 && (
        <>
          <div className="file-list-head">
            <strong>{files.length} file{files.length > 1 ? 's' : ''} ready</strong>
            {!busy && <button className="link" onClick={() => setFiles([])}>Clear all</button>}
          </div>
          <ul className="file-list">
            {files.map((f) => (
              <li key={f.name} className={OK_EXT.test(f.name) ? '' : 'bad'}>
                {busy ? <span className="spinner tiny" /> : <FileText size={14} />}
                <span className="fname">{f.name}</span>
                <span className="muted small">{(f.size / 1024).toFixed(0)} KB</span>
                {!busy && <button className="icon-btn" onClick={() => setFiles(files.filter((x) => x !== f))} aria-label={`Remove ${f.name}`}><X size={14} /></button>}
              </li>
            ))}
          </ul>
          {invalid.length > 0 && <p className="warn small">{invalid.length} file(s) have an unexpected extension; the server will check their content.</p>}
          <button className="btn btn-primary btn-block" onClick={upload} disabled={busy}>
            {busy
              ? <Spinner label={`Reading, matching & ranking ${files.length} resume${files.length > 1 ? 's' : ''}…`} />
              : `Analyse ${files.length} resume${files.length > 1 ? 's' : ''}`}
          </button>
        </>
      )}

      {result && (
        <div className="upload-result">
          {result.added.length > 0 && <p className="ok"><CheckCircle2 size={14} /> {result.added.length} resume(s) parsed and scored.</p>}
          {result.added.filter((a) => a.parse_level && a.parse_level !== 'high').map((a) => (
            <p key={a.id} className="warn small"><AlertTriangle size={13} /> <strong>{a.filename}</strong>: parsed with {a.parse_level} confidence. {a.warnings?.[0]}</p>
          ))}
          {result.errors.map((e) => (
            <p key={e.filename} className="error small"><AlertTriangle size={13} /> <strong>{e.filename}</strong>: {e.error}</p>
          ))}
        </div>
      )}
    </Card>
  )
}
