import { useMemo, useState } from 'react'
import { Trophy, Download, Search, ArrowUpDown, Trash2, ChevronRight, Medal, ScanSearch } from 'lucide-react'
import { api, download } from '../api'
import { Avatar, Card, Chip, Help, ScoreBar, Spinner, Verdict, fmtYears } from './ui'
import { useToast } from './toast'

const VERDICTS = ['All', 'Strong match', 'Good match', 'Partial match', 'Weak match']
const MAX_CHIPS = 4
const MEDAL = ['#d4a017', '#9ca3af', '#b87333']

export default function RankingTable({ jobId, rows, selectedId, onSelect, onDelete }) {
  const [q, setQ] = useState('')
  const [verdict, setVerdict] = useState('All')
  const [sort, setSort] = useState({ key: 'score', dir: -1 })
  const [confirmId, setConfirmId] = useState(null)
  const [exporting, setExporting] = useState(false)
  const notify = useToast()

  async function exportCsv() {
    setExporting(true)
    try {
      const name = await download(api.exportUrl(jobId))
      notify(`Downloaded ${name} (${rows.length} candidate${rows.length === 1 ? '' : 's'})`)
    } catch (e) {
      notify(e.message, 'error')
    } finally {
      setExporting(false)
    }
  }

  const view = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return rows
      .filter((r) => verdict === 'All' || r.verdict === verdict)
      .filter((r) => !needle || r.name.toLowerCase().includes(needle) ||
        r.matched_skills.some((s) => s.toLowerCase().includes(needle)) ||
        (r.current_title || '').toLowerCase().includes(needle))
      .sort((a, b) => {
        const va = a[sort.key], vb = b[sort.key]
        if (typeof va === 'string') return sort.dir * va.localeCompare(vb)
        return sort.dir * ((va ?? -1) - (vb ?? -1))
      })
  }, [rows, q, verdict, sort])

  const sortBy = (key) => setSort((s) => ({ key, dir: s.key === key ? -s.dir : key === 'name' ? 1 : -1 }))
  const Th = ({ k, children, className, extra }) => (
    <th className={`sortable ${className || ''}`} onClick={() => sortBy(k)}
        aria-sort={sort.key === k ? (sort.dir > 0 ? 'ascending' : 'descending') : 'none'}>
      {children} <ArrowUpDown size={12} className={sort.key === k ? 'active' : ''} />{extra}
    </th>
  )

  function handleDelete(e, r) {
    e.stopPropagation()
    if (confirmId === r.id) { onDelete(r); setConfirmId(null) } else { setConfirmId(r.id); setTimeout(() => setConfirmId(null), 3000) }
  }

  return (
    <Card
      title="Candidate ranking" icon={<Trophy size={18} />}
      actions={rows.length > 0 && (
        <button className="btn btn-ghost btn-sm" onClick={exportCsv} disabled={exporting}>
          {exporting ? <Spinner label="Exporting…" /> : <><Download size={14} /> Export CSV</>}
        </button>
      )}
    >
      {rows.length === 0 ? (
        <div className="empty">
          <Trophy size={28} />
          <p><strong>No candidates yet</strong></p>
          <p className="muted small">Upload resumes above. They will be ranked here, best match first.</p>
        </div>
      ) : (
        <>
          <div className="table-tools">
            <div className="search">
              <Search size={14} />
              <input placeholder="Search by name, title or skill…" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <div className="seg" role="group" aria-label="Filter by match level">
              {VERDICTS.map((v) => (
                <button key={v} className={verdict === v ? 'on' : ''} onClick={() => setVerdict(v)}>
                  {v === 'All' ? 'All' : v.replace(' match', '')}
                  <span className="count">{v === 'All' ? rows.length : rows.filter((r) => r.verdict === v).length}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="table-wrap">
            <table className="ranking">
              <thead>
                <tr>
                  <Th k="rank" className="num">#</Th>
                  <Th k="name">Candidate</Th>
                  <Th k="total_years">Experience</Th>
                  <Th k="score" extra={
                    <Help label="How is Match % calculated?">
                      <strong>Match % = weighted sum of 5 parts</strong>
                      <ul>
                        <li>Required skills: 40%</li>
                        <li>Relevant experience: 20%</li>
                        <li>Semantic fit with JD duties: 20%</li>
                        <li>Nice-to-have &amp; soft skills: 10%</li>
                        <li>Education: 10%</li>
                      </ul>
                      Open a candidate to see their exact breakdown.
                    </Help>
                  }>Match %</Th>
                  <th>Matched skills</th>
                  <th>Gaps</th>
                  <th aria-label="actions" />
                </tr>
              </thead>
              <tbody>
                {view.map((r) => (
                  <tr key={r.id} className={`${r.id === selectedId ? 'selected' : ''} ${r.rank <= 3 ? 'top' : ''}`}
                      onClick={() => onSelect(r.id)} tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && onSelect(r.id)}>
                    <td className="num rank">
                      {r.rank <= 3 ? <Medal size={18} color={MEDAL[r.rank - 1]} aria-label={`Rank ${r.rank}`} /> : r.rank}
                    </td>
                    <td>
                      <div className="cand">
                        <Avatar name={r.name} />
                        <div>
                          <div className="cand-name">
                            {r.name}
                            {r.parse_level && r.parse_level !== 'high' && (
                              <span className={`parse-flag ${r.parse_level}`}
                                    title={`Parse confidence ${r.parse_confidence}% (${r.parse_level}): ${r.parse_issues} issue(s). Check the original file before deciding.`}>
                                <ScanSearch size={12} /> {r.parse_level === 'low' ? 'check file' : 'review'}
                              </span>
                            )}
                          </div>
                          <div className="muted small">{r.current_title || r.filename}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <div>{fmtYears(r.total_years)}</div>
                      <div className="muted small">{fmtYears(r.relevant_years)} relevant</div>
                    </td>
                    <td className="score-cell">
                      <ScoreBar score={r.score} />
                      <Verdict verdict={r.verdict} score={r.score} />
                    </td>
                    <td>
                      <div className="chips">
                        {r.matched_skills.slice(0, MAX_CHIPS).map((s) => <Chip key={s} kind="match">{s}</Chip>)}
                        {r.matched_skills.length > MAX_CHIPS && <Chip title={r.matched_skills.slice(MAX_CHIPS).join(', ')}>+{r.matched_skills.length - MAX_CHIPS} more</Chip>}
                        {r.matched_skills.length === 0 && <span className="muted small">none</span>}
                      </div>
                    </td>
                    <td>
                      {r.missing_skills.length === 0
                        ? <span className="ok small">No gaps</span>
                        : <span className="miss-count" title={`Missing: ${r.missing_skills.join(', ')}`}>{r.missing_skills.length} missing</span>}
                      {r.partial_skills.length > 0 && <div className="muted small">{r.partial_skills.length} partial</div>}
                    </td>
                    <td className="row-actions">
                      <span className="view-link">View analysis <ChevronRight size={14} /></span>
                      <button className={`icon-btn ${confirmId === r.id ? 'confirm' : ''}`}
                              title={confirmId === r.id ? 'Click again to remove' : 'Remove candidate'}
                              onClick={(e) => handleDelete(e, r)}>
                        <Trash2 size={14} />{confirmId === r.id && <span className="small">Remove?</span>}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {view.length === 0 && <p className="empty muted">No candidates match this filter.</p>}
          </div>
        </>
      )}
    </Card>
  )
}
