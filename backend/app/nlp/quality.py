"""Parse-quality checks: how much should a recruiter trust this parse?

Each check returns pass / warn / fail with a plain-language message. The
weighted share of passed checks becomes a 0-100 confidence and a level
(high / medium / low). Low-confidence candidates are flagged in the ranking
so a human looks at the original file before rejecting anyone.
"""

from __future__ import annotations

# (check id, weight). Weights reflect how badly a failure distorts the match score.
WEIGHTS = {
    "text_quality": 3, "name": 2, "contact": 2, "experience_dates": 3, "skills": 3,
    "education": 1, "structure": 1, "years_consistency": 1, "ocr": 1, "file": 1,
}


def _check(cid: str, status: str, message: str) -> dict:
    return {"id": cid, "status": status, "message": message, "weight": WEIGHTS[cid]}


def assess(profile: dict, extraction: dict) -> dict:
    checks: list[dict] = []
    words = profile.get("word_count", 0)

    # --- text quality
    if words < 40:
        checks.append(_check("text_quality", "fail", f"Very little text extracted ({words} words); the file may be "
                                                     "mostly images or an unusual layout."))
    elif words < 120:
        checks.append(_check("text_quality", "warn", f"Short resume ({words} words); some details may be missing."))
    elif words > 2500:
        checks.append(_check("text_quality", "warn", f"Unusually long document ({words} words); "
                                                     "only the first pages may have been read."))
    else:
        checks.append(_check("text_quality", "pass", f"{words} words extracted."))

    # --- identity
    src = profile.get("field_sources", {}).get("name")
    if src in ("header", "ner"):
        checks.append(_check("name", "pass", f"Name found ({'top of resume' if src == 'header' else 'language model'})."))
    elif src == "email":
        checks.append(_check("name", "warn", "Name was inferred from the email address."))
    else:
        checks.append(_check("name", "fail", "No name found; using the file name."))

    has_email, has_phone = bool(profile.get("email")), bool(profile.get("phone"))
    if has_email and has_phone:
        status, msg = "pass", "Email and phone found."
        if profile.get("field_sources", {}).get("phone") == "unverified":
            status, msg = "warn", "Email found; phone number could not be validated."
        checks.append(_check("contact", status, msg))
    elif has_email or has_phone:
        checks.append(_check("contact", "warn", f"Only {'email' if has_email else 'phone'} found."))
    else:
        checks.append(_check("contact", "fail", "No email or phone found."))

    # --- experience
    roles = profile.get("experience", [])
    if roles:
        untitled = sum(1 for r in roles if r["title"] == "Role")
        status = "warn" if untitled else "pass"
        msg = f"{len(roles)} dated role(s) found" + (f"; {untitled} without a clear job title." if untitled else ".")
        checks.append(_check("experience_dates", status, msg))
    elif profile.get("claimed_years"):
        checks.append(_check("experience_dates", "warn", "No dated roles; experience taken from the summary "
                                                         f"({profile['claimed_years']:g}+ years)."))
    else:
        checks.append(_check("experience_dates", "fail", "No dated work history found; experience counted as 0."))

    n_skills = len(profile.get("technical_skills", []))
    checks.append(_check("skills", "pass" if n_skills >= 5 else "warn" if n_skills >= 2 else "fail",
                         f"{n_skills} technical skill(s) recognised."))

    checks.append(_check("education", "pass" if profile.get("education") else "warn",
                         "Degree found." if profile.get("education") else "No degree detected."))

    found = set(profile.get("sections_found", []))
    core = {"experience", "skills", "education"} & found
    checks.append(_check("structure", "pass" if len(core) >= 2 else "warn",
                         f"Standard sections found: {', '.join(sorted(core)) or 'none'}."))

    # --- consistency between what the resume claims and what the dates say
    claimed, computed = profile.get("claimed_years"), profile.get("computed_years")
    if claimed and computed is not None and abs(claimed - computed) > 2:
        checks.append(_check("years_consistency", "warn",
                             f"Resume claims {claimed:g}+ years but dated roles add up to {computed:g}."))
    else:
        checks.append(_check("years_consistency", "pass", "Stated and dated experience are consistent."))

    # --- extraction provenance
    if extraction.get("ocr_pages"):
        checks.append(_check("ocr", "warn", "Text was read with OCR from a scanned image; verify names and numbers."))
    else:
        checks.append(_check("ocr", "pass", "Native text layer (no OCR needed)."))
    file_warnings = [w for w in extraction.get("warnings", []) if not w.startswith("OCR was used")]
    checks.append(_check("file", "warn" if file_warnings else "pass",
                         "; ".join(file_warnings) if file_warnings else "File read without issues."))

    score = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
    total = sum(c["weight"] for c in checks)
    confidence = round(100 * sum(score[c["status"]] * c["weight"] for c in checks) / total)
    level = "high" if confidence >= 85 else "medium" if confidence >= 65 else "low"
    issues = [c["message"] for c in checks if c["status"] != "pass"] + profile.get("parse_notes", [])
    return {"confidence": confidence, "level": level, "checks": checks, "issues": issues}
