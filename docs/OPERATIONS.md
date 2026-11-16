# Operations guide

How MaxResume behaves in production: logging, the audit trail, resume ingestion
safeguards, configuration, security and deployment.

---

## 1. Logging

* **Format.** JSON lines when `ENV=production` (or `LOG_JSON=true`), readable text otherwise.
  One event per line, ready for Loki / ELK / CloudWatch.
* **Correlation.** Every request gets an id (`X-Request-ID`; a well-formed incoming id is honoured,
  otherwise one is generated) that is returned in the response header, attached to every log line,
  every audit entry and every error body. Quote it when reporting a problem.
* **Access log.** One line per API call: method, path, status, `duration_ms`, actor.
* **PII redaction.** Resumes are personal data. A logging filter masks email addresses
  (`j***@***`) and phone-like digit runs (`***42`) in every message and string field before it is
  written. Candidate names and resume text are never logged. Verified in `tests/test_production.py`.

```json
{"ts": "2026-11-16 12:35:01,469", "level": "INFO", "logger": "maxresume.access",
 "message": "POST /api/jobs/a851…/resumes 200", "request_id": "e0efe4002e044dc9", "actor": "alice",
 "http_method": "POST", "path": "/api/jobs/a851…/resumes", "status": 200, "duration_ms": 8570.3}
```

## 2. Audit trail

Stored in the `audit_log` collection; browsable in the UI (**Activity log** on a job) and via
`GET /api/audit?job_id=&action=&actor=&since=&limit=`.

| Action | Recorded details |
|---|---|
| `job.created` | title, source (paste/file), extracted counts |
| `job.updated` | field-level diff (skills added/removed, years/degree/weights from → to), candidates re-scored, scores changed |
| `job.deleted` | title, candidates deleted |
| `resume.ingested` | filename, SHA-256, size, type, extraction method, OCR pages, parse confidence, score, verdict, scorer version, batch id |
| `resume.rejected` | filename, reason code (`encrypted`, `corrupt`, `unsupported`, `zip_bomb`, `too_large`, `no_text`, `timeout`, `duplicate`), SHA-256 |
| `candidate.viewed` | access to a candidate's personal data |
| `candidate.file_downloaded` | access to the original file |
| `candidate.deleted` | filename, score at deletion |
| `ranking.exported` | format, rows |
| `audit.verified` | result of an integrity check |

Every entry has `seq`, `ts`, `actor`, `request_id`, `outcome`, `prev_hash` and `hash`.

**Tamper evidence.** `hash = SHA-256(canonical JSON of the entry, including prev_hash)`. Changing any
field of any entry, deleting an entry or reordering entries breaks the chain from that point.
`GET /api/audit/verify` (or **Verify integrity** in the UI) recomputes the whole chain and returns the first
broken sequence number. A unique index on `seq` makes concurrent writers (several API workers) safe:
the loser of a race reloads the chain head and retries.

> Limitations: an attacker with database write access could rewrite the *entire* chain consistently.
> For stronger guarantees, periodically export the head hash to an external, append-only store
> (e.g. object storage with object lock) and compare.

## 3. Resume ingestion safeguards

| Check | Behaviour |
|---|---|
| Type detection | by magic bytes, never by extension; mismatch is a warning, not an error |
| Size | `MAX_FILE_MB` (default 10); uploads are read with a bounded buffer |
| Zip bombs (DOCX/ODT) | total uncompressed size, entry count and compression ratio limits |
| Executables / images / archives | rejected (`unsupported`) |
| Password-protected PDF | rejected (`encrypted`) with a clear message |
| Damaged files | rejected (`corrupt`) |
| Long documents | first `MAX_PDF_PAGES` pages read, with a warning |
| Scanned PDFs | Tesseract OCR per page (up to `OCR_MAX_PAGES`); flagged in parse quality |
| Two-column layouts | gutter detection per page, read column by column |
| Legacy formats | `.doc/.rtf/.odt` converted with LibreOffice (isolated profile per conversion, timeout) |
| Duplicates | same file bytes **or** same normalised text for a job → rejected (`duplicate`) |
| Timeouts | `PARSE_TIMEOUT_S` per file; the batch continues |
| Concurrency | `PARSE_WORKERS` files parsed in parallel per process |
| Filenames | client paths/control characters stripped; download headers sanitised |
| CSV export | cells starting with `= + - @` are prefixed to prevent formula injection |

**Parse quality.** Each resume gets 10 checks (text quality, name, contact, dated roles, skills,
education, structure, claimed-vs-dated years, OCR, file warnings) → a 0–100 confidence and a level.
Medium/low confidence candidates are flagged in the ranking so a person checks the original file
before rejecting anyone.

## 4. Configuration

All settings are environment variables (see [`backend/.env.example`](../backend/.env.example)).

| Variable | Default | Notes |
|---|---|---|
| `ENV` | `development` | `production` switches on JSON logs |
| `LOG_LEVEL` / `LOG_JSON` | `INFO` / auto | |
| `STORAGE` | `auto` | `mongodb` fails fast if the DB is down; `memory` for tests |
| `MONGO_URL` / `MONGO_DB` | `mongodb://localhost:27017` / `maxresume` | |
| `API_KEYS` | *(empty)* | `name:key,…`; enables auth, names appear as the audit actor |
| `CORS_ORIGINS` | `http://localhost:5173,…` | comma-separated |
| `DEFAULT_PHONE_REGION` | `US` | for numbers written without a country code |
| `MAX_FILE_MB`, `MAX_BATCH`, `MAX_PDF_PAGES` | 10, 50, 15 | |
| `PARSE_TIMEOUT_S`, `PARSE_WORKERS` | 90, 4 | |
| `OCR_ENABLED`, `OCR_MAX_PAGES`, `OCR_DPI` | true, 6, 300 | |
| `ENABLE_SAMPLES` | true | turn off in production |

## 5. Security

* **Authentication.** Optional API keys (`X-API-Key`). With keys configured, every `/api` route except
  `/api/health` and `/api/ready` returns 401 without a valid key. The frontend sends `VITE_API_KEY` if
  built with one. For multi-user production use, put the app behind your SSO proxy and map users to keys.
* **Headers.** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`,
  `Cache-Control: no-store` on API responses.
* **Errors.** One shape everywhere: `{"detail", "error": {"code", "message", "request_id"}}`.
  Unhandled exceptions are logged with a stack trace and return a generic 500 (no internals leaked).
* **Data minimisation.** Logs never contain resume content; audit entries reference candidates by id
  and filename only.

## 6. Health & deployment

* `GET /api/health`: liveness (process up).
* `GET /api/ready`: readiness (database reachable **and** NLP models loaded); 503 until ready.

```bash
docker compose up --build        # MongoDB + API + web on http://localhost:8080
API_KEYS="recruiter:change-me" VITE_API_KEY="change-me" docker compose up --build   # with auth
```

The API image includes Tesseract, antiword and LibreOffice, bakes the embedding model in (no download at
start-up, `HF_HUB_OFFLINE=1`), runs as a non-root user and has a container health check.

## 7. Runbook

| Symptom | Check |
|---|---|
| Uploads rejected with `no_text` | scanned PDF and OCR disabled/unavailable: check `tesseract` is installed and `OCR_ENABLED` |
| `.doc/.rtf` rejected as `unsupported` | LibreOffice missing on the host |
| `/api/ready` returns 503 | `database:false`: MongoDB connectivity; `models_loaded:false`: model still loading or failed (see logs) |
| Many `timeout` rejections | raise `PARSE_TIMEOUT_S`, lower `OCR_MAX_PAGES`, or add workers/CPU |
| `audit.verified` with `ok:false` | treat as a security incident: the log was modified outside the application |
