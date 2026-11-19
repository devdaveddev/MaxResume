import { useEffect, useRef, useState } from 'react'
import { UploadCloud, FileText, X, AlertTriangle, Wand2, CheckCircle2 } from 'lucide-react'
import { api, samples } from '../api'
import { Card, Spinner } from './ui'
import { useToast } from './toast'



const CHUNK = 3


const DEFAULT_CONFIG = { max_batch: 50, max_file_mb: 10, formats: ['pdf', 'docx', 'doc', 'odt', 'rtf', 'txt'], ocr: true }

export default function Uploader({ jobId, onUploaded, compact, highlight, autoFiles, onAutoConsumed }) {
  const [files, setFiles] = useState([])
  const [busy, setBusy] = useState(false)
  const [loadingSamples, setLoadingSamples] = useState(false)
  const [drag, setDrag] = useState(false)
  const [result, setResult] = useState(null)
  const [progress, setProgress] = useState(null)
  const [config, setConfig] = useState(DEFAULT_CONFIG)
  const input = useRef(null)
  const notify = useToast()

  useEffect(() => { api.config().then(setConfig).catch(() => {}) }, [])


  const autoStarted = useRef(null)
  useEffect(() => {
    if (!autoFiles?.length || autoStarted.current === autoFiles) return
    autoStarted.current = autoFiles
    setFiles(autoFiles)
    upload(autoFiles)
    onAutoConsumed?.()
  }, [autoFiles])

  const okExt = new RegExp(`\\.(${config.formats.join('|')})$`, 'i')
  const formatList = config.formats.map((f) => f.toUpperCase()).join(', ')

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

  async function upload(selected = files) {
    const queue = [...selected]
    const total = { added: [], errors: [] }
    setBusy(true)
    setResult(null)
    setProgress({ done: 0, total: queue.length })
    for (let i = 0; i < queue.length; i += CHUNK) {
      const chunk = queue.slice(i, i + CHUNK)
      try {
        const res = await api.uploadResumes(jobId, chunk)
        total.added.push(...res.added)
        total.errors.push(...res.errors)
        onUploaded(res)
      } catch (err) {

        total.errors.push(...chunk.map((f) => ({ filename: f.name, error: err.message })))
      }
      setFiles((prev) => prev.filter((f) => !chunk.includes(f)))
      setProgress({ done: Math.min(i + CHUNK, queue.length), total: queue.length })
      setResult({ added: [...total.added], errors: [...total.errors] })
    }
    setBusy(false)
    setProgress(null)
    if (total.added.length) notify(`${total.added.length} candidate${total.added.length > 1 ? 's' : ''} analysed and ranked`)
    if (total.errors.length) notify(`${total.errors.length} file(s) could not be processed`, 'error')
  }

  const invalid = files.filter((f) => !okExt.test(f.name))
  const tooMany = files.length > config.max_batch

  return (
    <Card title={compact ? 'Add more resumes' : 'Step 2 · Upload resumes'} icon={<UploadCloud size={18} />}
          className={highlight ? 'highlight' : ''}
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
        <p className="muted small">
          {formatList} · select many at once (up to {config.max_batch}, max {config.max_file_mb} MB each)
          {config.ocr && ' · scanned PDFs are read with OCR'}
        </p>
        <input ref={input} type="file" multiple accept={config.formats.map((f) => `.${f}`).join(',')} hidden
               onChange={(e) => { addFiles(e.target.files); e.target.value = '' }} />
      </div>

      {progress && (
        <div className="upload-progress" role="progressbar" aria-valuemin={0} aria-valuemax={progress.total} aria-valuenow={progress.done}>
          <div className="up-head">
            <Spinner label={`Analysed ${progress.done} of ${progress.total} resume${progress.total > 1 ? 's' : ''}…`} />
            <span className="muted small">{Math.round((progress.done / progress.total) * 100)}%</span>
          </div>
          <div className="up-track"><div className="up-fill" style={{ width: `${Math.max(4, (progress.done / progress.total) * 100)}%` }} /></div>
          <p className="muted small">Candidates appear in the ranking below as soon as they are scored.</p>
        </div>
      )}

      {files.length > 0 && (
        <>
          <div className="file-list-head">
            <strong>{files.length} file{files.length > 1 ? 's' : ''} ready</strong>
            {!busy && <button className="link" onClick={() => setFiles([])}>Clear all</button>}
          </div>
          <ul className="file-list">
            {files.map((f) => (
              <li key={f.name} className={okExt.test(f.name) ? '' : 'bad'}>
                {busy ? <span className="spinner tiny" /> : <FileText size={14} />}
                <span className="fname">{f.name}</span>
                <span className="muted small">{(f.size / 1024).toFixed(0)} KB</span>
                {!busy && <button className="icon-btn" onClick={() => setFiles(files.filter((x) => x !== f))} aria-label={`Remove ${f.name}`}><X size={14} /></button>}
              </li>
            ))}
          </ul>
          {invalid.length > 0 && <p className="warn small">{invalid.length} file(s) are not in a supported format ({formatList}); the server will check their content.</p>}
          {tooMany && <p className="warn small">This server accepts up to {config.max_batch} resumes per batch; remove {files.length - config.max_batch}.</p>}
          <button className="btn btn-primary btn-block" onClick={() => upload()} disabled={busy || tooMany}>
            {busy
              ? <Spinner label={`${files.length} waiting…`} />
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
