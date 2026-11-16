// Thin wrapper around the FastAPI backend. All paths are proxied by Vite in dev.
// When the API runs with API_KEYS, set VITE_API_KEY at build time to send it.
const API_KEY = import.meta.env.VITE_API_KEY

function withAuth(options = {}) {
  return API_KEY ? { ...options, headers: { ...(options.headers || {}), 'X-API-Key': API_KEY } } : options
}

async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, withAuth(options))
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`
    let requestId = res.headers.get('x-request-id')
    try {
      const body = await res.json()
      msg = body.error?.message || (typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail))
      requestId = body.error?.request_id || requestId
    } catch { /* non-JSON error */ }
    const err = new Error(msg)
    err.requestId = requestId
    throw err
  }
  return res.status === 204 ? null : res.json()
}

export const api = {
  health: () => request('/health'),
  skills: () => request('/skills'),
  listJobs: () => request('/jobs'),
  getJob: (id) => request(`/jobs/${id}`),
  createJob: ({ text, title, file }) => {
    const form = new FormData()
    if (text) form.append('text', text)
    if (title) form.append('title', title)
    if (file) form.append('file', file)
    return request('/jobs', { method: 'POST', body: form })
  },
  updateJob: (id, body) =>
    request(`/jobs/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  deleteJob: (id) => request(`/jobs/${id}`, { method: 'DELETE' }),
  uploadResumes: (jobId, files) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    return request(`/jobs/${jobId}/resumes`, { method: 'POST', body: form })
  },
  candidates: (jobId) => request(`/jobs/${jobId}/candidates`),
  candidate: (id) => request(`/candidates/${id}`),
  deleteCandidate: (id) => request(`/candidates/${id}`, { method: 'DELETE' }),
  fileUrl: (id) => `/api/candidates/${id}/file`,
  exportUrl: (jobId) => `/api/jobs/${jobId}/export.csv`,
  audit: (params = {}) => request(`/audit?${new URLSearchParams(params)}`),
  verifyAudit: () => request('/audit/verify'),
  config: () => request('/config'),
}

// Demo helpers: fetch bundled synthetic samples and turn them into File objects,
// so they go through exactly the same upload path as a real recruiter's files.
export const samples = {
  list: () => request('/samples'),
  resumeFiles: async (names, group = 'resumes') => Promise.all(names.map(async (name) => {
    const res = await fetch(`/api/samples/${group}/${encodeURIComponent(name)}`, withAuth())
    return new File([await res.blob()], name, { type: res.headers.get('content-type') || '' })
  })),
}

// Downloads go through fetch (not a plain <a href>) so the API key header is sent when auth is on.
export async function download(url, { open = false } = {}) {
  const res = await fetch(url, withAuth())
  if (!res.ok) throw new Error(`Download failed (${res.status})`)
  const blob = await res.blob()
  const objectUrl = URL.createObjectURL(blob)
  const name = (res.headers.get('content-disposition') || '').match(/filename="([^"]+)"/)?.[1] || 'download'
  if (open) {
    window.open(objectUrl, '_blank', 'noopener')
  } else {
    const a = Object.assign(document.createElement('a'), { href: objectUrl, download: name })
    document.body.appendChild(a)
    a.click()
    a.remove()
  }
  setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
}
