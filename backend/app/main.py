"""FastAPI application: HTTP routes for jobs, resume uploads, results and the audit trail."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import logging
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import PurePath

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import service
from .audit import AuditLog, public_entry
from .config import get_settings
from .db import create_store
from .ingest.detect import EXTENSIONS, MEDIA_TYPES, FileRejected
from .logging_setup import request_id_var, setup_logging
from .matching.scorer import DEFAULT_WEIGHTS
from .middleware import RequestContextMiddleware
from .nlp import embeddings
from .nlp.skills_taxonomy import SKILLS
from .nlp.text_extract import extract_text

settings = get_settings()
setup_logging(settings.log_level, settings.use_json_logs)
log = logging.getLogger("maxresume")

MAX_JD_CHARS = 50_000


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.store = await create_store()
    app.state.audit = AuditLog(app.state.store)
    app.state.models_ready = False
    app.state.parse_slots = asyncio.Semaphore(settings.parse_workers)
    log.info("Starting MaxResume", extra={"version": settings.app_version, "env": settings.env,
                                          "storage": app.state.store.kind, "auth": bool(settings.api_key_map)})
    # Load the embedding model + spaCy in the background so the first upload is fast.
    asyncio.get_running_loop().run_in_executor(None, _warm_up, app)
    yield
    log.info("Shutting down")


def _warm_up(app: FastAPI) -> None:
    from .nlp.resume_parser import _nlp

    try:
        embeddings.encode(["warm up"])
        _nlp()
        app.state.models_ready = True
        log.info("NLP models loaded", extra={"embedding_model": embeddings.MODEL_NAME})
    except Exception:  # noqa: BLE001
        log.exception("Failed to load NLP models")


app = FastAPI(title="MaxResume API", version=settings.app_version, lifespan=lifespan,
              description="AI resume matching & candidate ranking")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["*"],
                   allow_headers=["*"], expose_headers=["X-Request-ID"])
app.add_middleware(RequestContextMiddleware)


def store():
    return app.state.store


def audit() -> AuditLog:
    return app.state.audit


# --------------------------------------------------------------------------- errors
# One error shape everywhere: {"detail": msg, "error": {"code", "message", "request_id"}}

def _error(status: int, code: str, message: str, extra: dict | None = None) -> JSONResponse:
    body = {"detail": message, "error": {"code": code, "message": message, "request_id": request_id_var.get()}}
    if extra:
        body["error"].update(extra)
    return JSONResponse(status_code=status, content=body)


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    code = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 409: "conflict",
            413: "too_large", 422: "invalid", 429: "rate_limited"}.get(exc.status_code, "error")
    return _error(exc.status_code, code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    fields = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return _error(422, "invalid", "Request validation failed.", {"fields": fields})


@app.exception_handler(Exception)
async def unhandled_error(_: Request, exc: Exception):
    log.exception("Unhandled error", extra={"error_type": type(exc).__name__})
    return _error(500, "internal", "Something went wrong on our side. Quote the request id when reporting it.")


async def _job_or_404(job_id: str) -> dict:
    job = await store().get("jobs", job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


def _safe_filename(name: str | None) -> str:
    """Strip any client-supplied path and control characters; keep a readable, bounded name."""
    base = PurePath((name or "resume").replace("\\", "/")).name
    base = re.sub(r"[\x00-\x1f\x7f\"<>|]", "", base).strip(". ") or "resume"
    return base[:150]


# --------------------------------------------------------------------------- meta

@app.get("/api/health")
async def health():
    """Liveness: the process is up."""
    return {"status": "ok", "version": settings.app_version, "storage": store().kind,
            "embedding_model": embeddings.MODEL_NAME, "auth": bool(settings.api_key_map)}


@app.get("/api/ready")
async def ready():
    """Readiness: database reachable and NLP models loaded."""
    db_ok = await store().ping()
    ok = db_ok and app.state.models_ready
    body = {"ready": ok, "database": db_ok, "models_loaded": app.state.models_ready}
    return JSONResponse(status_code=200 if ok else 503, content=body)


@app.get("/api/skills")
async def skills():
    return [{"name": k, "category": v["category"]} for k, v in sorted(SKILLS.items())]


# --------------------------------------------------------------------------- demo samples
# Synthetic sample data so a reviewer can try the app in one click (disable with ENABLE_SAMPLES=false).

SAMPLE_GROUPS = {"resumes", "edge_cases"}


@app.get("/api/samples")
async def samples():
    if not settings.enable_samples:
        return {"job_descriptions": [], "resumes": [], "edge_cases": []}
    root = settings.samples_dir
    jd_dir = root / "job_descriptions"
    jds = [{"name": p.stem.replace("_", " ").title(), "text": p.read_text()}
           for p in sorted(jd_dir.glob("*.txt"))] if jd_dir.exists() else []
    out = {"job_descriptions": jds}
    for group in SAMPLE_GROUPS:
        d = root / group
        out[group] = sorted(p.name for p in d.iterdir() if p.suffix in EXTENSIONS) if d.exists() else []
    return out


@app.get("/api/samples/{group}/{name}")
async def sample_file(group: str, name: str):
    if not settings.enable_samples or group not in SAMPLE_GROUPS:
        raise HTTPException(404, "Sample not found")
    base = (settings.samples_dir / group).resolve()
    path = (base / name).resolve()
    if path.parent != base or not path.is_file():  # no path traversal
        raise HTTPException(404, "Sample not found")
    return FileResponse(path)


# --------------------------------------------------------------------------- jobs

@app.post("/api/jobs", status_code=201)
async def create_job(text: str | None = Form(None, max_length=MAX_JD_CHARS), title: str | None = Form(None, max_length=200),
                     file: UploadFile | None = File(None)):
    """Create a job from pasted text and/or an uploaded JD file."""
    source = "paste"
    if file and file.filename:
        data = await file.read(settings.max_file_bytes + 1)
        try:
            text = await run_in_threadpool(extract_text, _safe_filename(file.filename), data)
        except FileRejected as e:
            raise HTTPException(400, str(e)) from e
        source = "file"
    if not text or len(text.strip()) < 50:
        raise HTTPException(400, "Please paste or upload a job description (at least 50 characters).")
    job = await run_in_threadpool(service.build_job, text.strip()[:MAX_JD_CHARS], (title or "").strip() or None)
    await store().insert("jobs", job)
    p = job["parsed"]
    await audit().record("job.created", target_type="job", target_id=job["_id"], job_id=job["_id"], details={
        "title": job["title"], "source": source, "chars": len(job["text"]),
        "required_skills": len(p["required_skills"]), "preferred_skills": len(p["preferred_skills"]),
        "min_years": p.get("min_years"), "education_min_level": p["education"]["min_level"]})
    return service.public_job(job, 0)


@app.get("/api/jobs")
async def list_jobs():
    jobs = await store().find("jobs", {}, {"title": 1, "created_at": 1})
    out = [{"id": j["_id"], "title": j["title"], "created_at": j["created_at"],
            "candidate_count": await store().count("candidates", {"job_id": j["_id"]})} for j in jobs]
    return sorted(out, key=lambda j: j["created_at"], reverse=True)


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = await _job_or_404(job_id)
    return service.public_job(job, await store().count("candidates", {"job_id": job_id}))


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    required_skills: list[str] | None = Field(default=None, max_length=100)
    preferred_skills: list[str] | None = Field(default=None, max_length=100)
    min_years: float | None = Field(default=None, ge=0, le=40)
    education_min_level: int | None = Field(default=None, ge=0, le=4)
    weights: dict[str, float] | None = None

    @field_validator("required_skills", "preferred_skills")
    @classmethod
    def _skill_names(cls, v):
        if v is not None and any(len(s) > 60 for s in v):
            raise ValueError("skill names must be at most 60 characters")
        return v

    @field_validator("weights")
    @classmethod
    def _weights(cls, v):
        if v is None:
            return v
        unknown = set(v) - set(DEFAULT_WEIGHTS)
        if unknown:
            raise ValueError(f"unknown weight(s): {', '.join(sorted(unknown))}")
        if any(not 0 <= x <= 1 for x in v.values()):
            raise ValueError("weights must be between 0 and 1")
        if sum(v.values()) <= 0:
            raise ValueError("at least one weight must be positive")
        return v


@app.put("/api/jobs/{job_id}")
async def update_job(job_id: str, body: JobUpdate):
    """Apply recruiter corrections to the extracted requirements and rescore every candidate."""
    job = await _job_or_404(job_id)
    before = service.job_snapshot(job)
    job = service.apply_job_edits(job, body.model_dump(exclude_unset=True))
    changes = service.diff(before, service.job_snapshot(job))
    await store().update("jobs", job_id, {"title": job["title"], "parsed": job["parsed"], "weights": job["weights"]})
    cands = await store().find("candidates", {"job_id": job_id}, {"profile": 1, "match": 1})
    score_changes = 0
    for c in cands:
        match = await run_in_threadpool(service.rescore, job, c)
        score_changes += abs(match["score"] - c["match"]["score"]) >= 0.1
        await store().update("candidates", c["_id"], {"match": match})
    await audit().record("job.updated", target_type="job", target_id=job_id, job_id=job_id,
                         details={"changes": changes, "rescored": len(cands), "scores_changed": score_changes})
    return service.public_job(job, len(cands))


@app.delete("/api/jobs/{job_id}", status_code=204)
async def delete_job(job_id: str):
    job = await _job_or_404(job_id)
    cands = await store().find("candidates", {"job_id": job_id}, {"_id": 1})
    for c in cands:
        await store().delete("files", {"_id": c["_id"]})
    await store().delete("candidates", {"job_id": job_id})
    await store().delete("jobs", {"_id": job_id})
    await audit().record("job.deleted", target_type="job", target_id=job_id, job_id=job_id,
                         details={"title": job["title"], "candidates_deleted": len(cands)})
    return Response(status_code=204)


# --------------------------------------------------------------------------- resumes

async def _process_one(job: dict, f: UploadFile) -> dict:
    """Read, validate, extract, parse and score one upload. Never raises: returns ok/error."""
    name = _safe_filename(f.filename)
    data = await f.read(settings.max_file_bytes + 1)  # bounded read: never buffer more than the limit
    sha = hashlib.sha256(data).hexdigest()
    try:
        async with app.state.parse_slots:  # bound concurrent CPU work
            cand = await asyncio.wait_for(run_in_threadpool(service.process_resume, job, name, data),
                                          timeout=settings.parse_timeout_s)
        return {"ok": True, "name": name, "data": data, "cand": cand}
    except FileRejected as e:
        return {"ok": False, "name": name, "code": e.code, "error": str(e), "sha": sha, "size": len(data)}
    except asyncio.TimeoutError:
        log.warning("Parsing timed out", extra={"upload": name, "timeout_s": settings.parse_timeout_s})
        return {"ok": False, "name": name, "code": "timeout", "sha": sha, "size": len(data),
                "error": f"Processing took longer than {settings.parse_timeout_s:g}s and was stopped."}
    except Exception as e:  # noqa: BLE001 - report and continue with the batch
        log.exception("Failed to process upload", extra={"upload": name})
        return {"ok": False, "name": name, "code": "parse_error", "sha": sha, "size": len(data),
                "error": f"Could not parse this file ({type(e).__name__})."}


@app.post("/api/jobs/{job_id}/resumes")
async def upload_resumes(job_id: str, files: list[UploadFile] = File(...)):
    """Batch upload. Files are processed in parallel (bounded) and independently:
    one bad file never fails the batch."""
    job = await _job_or_404(job_id)
    if len(files) > settings.max_batch:
        raise HTTPException(400, f"Upload at most {settings.max_batch} resumes per batch.")
    batch_id = uuid.uuid4().hex[:12]
    log.info("Batch upload started", extra={"job_id": job_id, "batch_id": batch_id, "files": len(files)})
    results = await asyncio.gather(*(_process_one(job, f) for f in files))

    existing = await store().find("candidates", {"job_id": job_id}, {"text_hash": 1, "file_sha256": 1})
    seen_text = {c.get("text_hash") for c in existing}
    seen_file = {c.get("file_sha256") for c in existing}
    added, errors = [], []
    for r in results:
        if not r["ok"]:
            errors.append({"filename": r["name"], "code": r["code"], "error": r["error"]})
            await audit().record("resume.rejected", target_type="file", job_id=job_id, outcome="rejected", details={
                "filename": r["name"], "code": r["code"], "reason": r["error"], "sha256": r["sha"],
                "size_bytes": r["size"], "batch_id": batch_id})
            continue
        cand = r["cand"]
        if cand["file_sha256"] in seen_file or cand["text_hash"] in seen_text:
            msg = "Duplicate: this resume was already uploaded for this job."
            errors.append({"filename": r["name"], "code": "duplicate", "error": msg})
            await audit().record("resume.rejected", target_type="file", job_id=job_id, outcome="rejected", details={
                "filename": r["name"], "code": "duplicate", "reason": msg, "sha256": cand["file_sha256"],
                "batch_id": batch_id})
            continue
        seen_file.add(cand["file_sha256"])
        seen_text.add(cand["text_hash"])
        await store().insert("candidates", cand)
        await store().insert("files", {"_id": cand["_id"], "filename": r["name"], "file_type": cand["file_type"],
                                       "sha256": cand["file_sha256"], "data": r["data"]})
        q, ex, m = cand["quality"], cand["extraction"], cand["match"]
        await audit().record("resume.ingested", target_type="candidate", target_id=cand["_id"], job_id=job_id,
                             details={"filename": r["name"], "sha256": cand["file_sha256"],
                                      "size_bytes": ex["size_bytes"], "file_type": ex["file_type"],
                                      "extraction_method": ex["method"], "ocr_pages": ex["ocr_pages"],
                                      "parse_confidence": q["confidence"], "parse_level": q["level"],
                                      "score": m["score"], "verdict": m["verdict"],
                                      "scorer_version": m["meta"]["scorer_version"], "batch_id": batch_id})
        summary = service.summary(cand)
        summary["warnings"] = q["issues"][:5]
        added.append(summary)
    log.info("Batch upload finished", extra={"job_id": job_id, "batch_id": batch_id,
                                             "added": len(added), "rejected": len(errors)})
    return {"batch_id": batch_id, "added": sorted(added, key=lambda c: -c["score"]), "errors": errors}


@app.get("/api/jobs/{job_id}/candidates")
async def list_candidates(job_id: str):
    await _job_or_404(job_id)
    cands = await store().find("candidates", {"job_id": job_id}, {"raw_text": 0, "profile.chunks": 0})
    rows = sorted((service.summary(c) for c in cands), key=lambda r: (-r["score"], r["name"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def _csv_safe(value) -> str:
    """Neutralise spreadsheet formula injection (cells starting with = + - @ are prefixed)."""
    s = "" if value is None else str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


@app.get("/api/jobs/{job_id}/export.csv")
async def export_csv(job_id: str):
    job = await _job_or_404(job_id)
    rows = await list_candidates(job_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Rank", "Candidate", "Email", "Experience (yrs)", "Relevant (yrs)", "Match %", "Verdict",
                "Matched skills", "Missing skills", "Parse confidence", "File"])
    for r in rows:
        w.writerow([_csv_safe(x) for x in (
            r["rank"], r["name"], r["email"], r["total_years"], r["relevant_years"], r["score"], r["verdict"],
            "; ".join(r["matched_skills"]), "; ".join(r["missing_skills"]), r["parse_confidence"], r["filename"])])
    await audit().record("ranking.exported", target_type="job", target_id=job_id, job_id=job_id,
                         details={"format": "csv", "rows": len(rows)})
    fname = re.sub(r"[^A-Za-z0-9]+", "_", job["title"])[:40].strip("_") or "ranking"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{fname}_ranking.csv"'})


# --------------------------------------------------------------------------- candidates

@app.get("/api/candidates/{cand_id}")
async def get_candidate(cand_id: str):
    c = await store().get("candidates", cand_id)
    if not c:
        raise HTTPException(404, "Candidate not found")
    job = await _job_or_404(c["job_id"])
    out = service.public_candidate(c)
    out["job"] = {"id": job["_id"], "title": job["title"], "parsed": job["parsed"],
                  "weights": job.get("weights", DEFAULT_WEIGHTS)}
    # access to personal data is audited
    await audit().record("candidate.viewed", target_type="candidate", target_id=cand_id, job_id=c["job_id"])
    return out


@app.get("/api/candidates/{cand_id}/file")
async def get_candidate_file(cand_id: str):
    f = await store().get("files", cand_id)
    if not f:
        raise HTTPException(404, "File not found")
    cand = await store().get("candidates", cand_id)
    await audit().record("candidate.file_downloaded", target_type="candidate", target_id=cand_id,
                         job_id=cand["job_id"] if cand else None, details={"sha256": f.get("sha256")})
    kind = f.get("file_type") or f["filename"].rsplit(".", 1)[-1].lower()
    safe = re.sub(r'[^\w.\- ]', "_", f["filename"])
    return Response(content=bytes(f["data"]), media_type=MEDIA_TYPES.get(kind, "application/octet-stream"),
                    headers={"Content-Disposition": f'inline; filename="{safe}"'})


@app.delete("/api/candidates/{cand_id}", status_code=204)
async def delete_candidate(cand_id: str):
    c = await store().get("candidates", cand_id)
    if not c:
        raise HTTPException(404, "Candidate not found")
    await store().delete("candidates", {"_id": cand_id})
    await store().delete("files", {"_id": cand_id})
    await audit().record("candidate.deleted", target_type="candidate", target_id=cand_id, job_id=c["job_id"],
                         details={"filename": c["filename"], "score": c["match"]["score"]})
    return Response(status_code=204)


# --------------------------------------------------------------------------- audit

@app.get("/api/audit")
async def list_audit(job_id: str | None = None, action: str | None = None, actor: str | None = None,
                     since: str | None = None, limit: int = Query(200, ge=1, le=1000)):
    entries = await audit().list(job_id=job_id, action=action, actor=actor, since=since, limit=limit)
    return [public_entry(e) for e in entries]


@app.get("/api/audit/verify")
async def verify_audit():
    """Recompute the hash chain over the entire audit log and report any tampering."""
    result = await audit().verify()
    await audit().record("audit.verified", target_type="audit_log", outcome="success" if result["ok"] else "failure",
                         details={k: v for k, v in result.items() if k != "head_hash"})
    if not result["ok"]:
        log.error("Audit chain verification FAILED", extra={"reason": result.get("reason"),
                                                             "broken_at_seq": result.get("broken_at_seq")})
    return result


# --------------------------------------------------------------------------- single-container mode
# In the all-in-one image (e.g. Hugging Face Spaces) the built React app is served by this process.
# Mounted last so every /api route above takes precedence.
if settings.static_dir and settings.static_dir.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="web")
