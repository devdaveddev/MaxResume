"""Application logic that sits between the HTTP layer and the NLP/scoring code."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from .config import get_settings
from .matching.scorer import DEFAULT_WEIGHTS, SCORER_VERSION, score_candidate
from .nlp.education import LEVEL_NAMES
from .nlp.jd_parser import parse_jd
from .nlp.quality import assess
from .nlp.resume_parser import parse_resume
from .nlp.text_extract import extract, normalize_text


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def build_job(text: str, title: str | None) -> dict:
    # Pasted text gets the same cleanup as uploaded files: browsers submit
    # textareas with CRLF line endings, and pasted JDs often contain bullet glyphs.
    text = normalize_text(text)
    parsed = parse_jd(text, title)
    return {"_id": new_id(), "title": parsed["title"], "text": text, "parsed": parsed,
            "weights": dict(DEFAULT_WEIGHTS), "created_at": now()}


def apply_job_edits(job: dict, edits: dict) -> dict:
    """Recruiter corrections to the extracted requirements (then everything is rescored)."""
    p = job["parsed"]
    if edits.get("title"):
        job["title"] = p["title"] = edits["title"]
    for key in ("required_skills", "preferred_skills"):
        if edits.get(key) is not None:
            p[key] = list(dict.fromkeys(s.strip() for s in edits[key] if s.strip()))
    # a skill can't be both required and preferred
    p["preferred_skills"] = [s for s in p["preferred_skills"] if s not in p["required_skills"]]
    p["alternatives"] = [g for g in p.get("alternatives", [])
                         if set(g) <= set(p["required_skills"]) or set(g) <= set(p["preferred_skills"])]
    if "min_years" in edits:
        p["min_years"] = edits["min_years"]
        if p.get("max_years") and edits["min_years"] and p["max_years"] < edits["min_years"]:
            p["max_years"] = None
    if edits.get("education_min_level") is not None:
        lvl = int(edits["education_min_level"])
        p["education"]["min_level"] = lvl
        p["education"]["min_level_name"] = LEVEL_NAMES.get(lvl)
    if edits.get("weights"):
        job["weights"] = {k: max(0.0, float(edits["weights"].get(k, v))) for k, v in DEFAULT_WEIGHTS.items()}
    return job


def scoring_meta(job: dict) -> dict:
    """Provenance stored with every score so it can be explained and reproduced later."""
    return {"scored_at": now(), "scorer_version": SCORER_VERSION, "embedding_model": get_settings().embedding_model,
            "weights": job.get("weights", DEFAULT_WEIGHTS), "app_version": get_settings().app_version}


def process_resume(job: dict, filename: str, data: bytes) -> dict:
    """Extract -> parse -> quality-check -> score one resume. CPU-bound; called in a worker thread."""
    ex = extract(filename, data)
    profile = parse_resume(ex.text, filename, links=ex.links)
    quality = assess(profile, ex.meta())
    match = score_candidate(job["parsed"], profile, job.get("weights"))
    match["meta"] = scoring_meta(job)
    return {
        "_id": new_id(),
        "job_id": job["_id"],
        "filename": filename,
        "file_type": ex.file_type,
        "file_sha256": ex.sha256,
        "uploaded_at": now(),
        "text_hash": hashlib.sha256(" ".join(ex.text.split()).lower().encode()).hexdigest(),
        "raw_text": ex.text,
        "extraction": ex.meta(),
        "quality": quality,
        "profile": profile,
        "match": match,
    }


def rescore(job: dict, cand: dict) -> dict:
    match = score_candidate(job["parsed"], cand["profile"], job.get("weights"))
    match["meta"] = scoring_meta(job)
    return match


def job_snapshot(job: dict) -> dict:
    """The recruiter-editable parts of a job, used to diff edits for the audit log."""
    p = job["parsed"]
    return {"title": job["title"], "required_skills": p["required_skills"], "preferred_skills": p["preferred_skills"],
            "min_years": p.get("min_years"), "education_min_level": p["education"]["min_level"],
            "weights": job.get("weights", DEFAULT_WEIGHTS)}


def diff(before: dict, after: dict) -> dict:
    out = {}
    for k in after:
        if before.get(k) != after[k]:
            b, a = before.get(k), after[k]
            if isinstance(a, list) and isinstance(b, list):
                out[k] = {"added": [x for x in a if x not in b], "removed": [x for x in b if x not in a]}
            else:
                out[k] = {"from": b, "to": a}
    return out


def summary(c: dict) -> dict:
    """Compact row for the ranking table."""
    p, m = c["profile"], c["match"]
    sk = m["skills"]
    return {
        "id": c["_id"],
        "name": p["name"],
        "email": p.get("email"),
        "current_title": p.get("current_title"),
        "filename": c["filename"],
        "total_years": p.get("total_years"),
        "relevant_years": m["experience"]["relevant_years"],
        "score": m["score"],
        "verdict": m["verdict"],
        "matched_skills": [x["skill"] for x in sk["matched"]],
        "partial_skills": [x["skill"] for x in sk["partial"]],
        "missing_skills": [x["skill"] for x in sk["missing"]],
        "required_count": sk.get("required_count", 0),
        "highest_degree": p.get("highest_degree"),
        "breakdown": {b["key"]: b["points"] for b in m["breakdown"]},
        "parse_confidence": (c.get("quality") or {}).get("confidence"),
        "parse_level": (c.get("quality") or {}).get("level"),
        "parse_issues": len((c.get("quality") or {}).get("issues", [])),
    }


def public_job(job: dict, candidate_count: int | None = None) -> dict:
    out = {"id": job["_id"], "title": job["title"], "text": job["text"], "parsed": job["parsed"],
           "weights": job.get("weights", DEFAULT_WEIGHTS), "created_at": job["created_at"]}
    if candidate_count is not None:
        out["candidate_count"] = candidate_count
    return out


def public_candidate(c: dict) -> dict:
    profile = {k: v for k, v in c["profile"].items() if k != "chunks"}
    return {"id": c["_id"], "job_id": c["job_id"], "filename": c["filename"], "file_type": c["file_type"],
            "uploaded_at": c["uploaded_at"], "profile": profile, "match": c["match"], "raw_text": c["raw_text"],
            "extraction": c.get("extraction"), "quality": c.get("quality")}
