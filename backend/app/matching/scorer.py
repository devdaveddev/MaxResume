"""JD <-> resume matching and explainable scoring.

Overall score (0-100) = weighted average of five component scores in [0, 1]:

    component            default weight   what it measures
    -------------------  --------------   -----------------------------------------
    required_skills           0.40        coverage of the JD's must-have skills
    experience                0.20        relevant years vs. the JD's minimum
    semantic                  0.20        how well resume sentences cover JD requirement statements
    preferred_skills          0.10        coverage of nice-to-have + soft skills
    education                 0.10        degree level and field vs. the JD

If the JD does not specify something (no preferred skills, no years, no
degree) that component is dropped and the remaining weights are re-normalised,
so a candidate is never penalised for a requirement that does not exist.

Every component returns both a number and the evidence behind it; the
"reasons" list shown to recruiters is generated from that evidence.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from ..nlp.dates import total_months
from ..nlp.embeddings import cosine_matrix
from ..nlp.skills import extract_skills, find_skill_context
from ..nlp.skills_taxonomy import IMPLIED_BY, semantic_query, siblings

SCORER_VERSION = "2026.11.2"

DEFAULT_WEIGHTS = {
    "required_skills": 0.40,
    "experience": 0.20,
    "semantic": 0.20,
    "preferred_skills": 0.10,
    "education": 0.10,
}
LABELS = {
    "required_skills": "Required skills",
    "experience": "Relevant experience",
    "semantic": "Semantic fit (JD requirements)",
    "preferred_skills": "Preferred & soft skills",
    "education": "Education",
}

CREDIT_EXACT_USED = 1.00
CREDIT_EXACT_LISTED = 0.85
CREDIT_SIBLING = 0.50
CREDIT_SEMANTIC = 0.50
SKILL_SEMANTIC_THRESHOLD = 0.62

SEM_FLOOR, SEM_CEIL = 0.25, 0.70
ROLE_TITLE_THRESHOLD = 0.60
ROLE_TEXT_THRESHOLD = 0.50
UNRELATED_EXPERIENCE_FACTOR = 0.25
UNRELATED_MAX_SHARE = 0.5


def _calibrate(sim: float) -> float:
    return float(np.clip((sim - SEM_FLOOR) / (SEM_CEIL - SEM_FLOOR), 0.0, 1.0))



def _skill_credit(s: str, have: dict, full_text: str, sem_row, chunks: list[str], or_similar: bool) -> dict:
    """Best available evidence for one JD skill, in priority order:
    exact mention > substitute from same family > semantic evidence > missing."""
    if s in have:
        used = have[s]["used_in_experience"]
        return {"skill": s, "credit": CREDIT_EXACT_USED if used else CREDIT_EXACT_LISTED, "status": "matched",
                "how": "used in experience" if used else "listed", "evidence": find_skill_context(s, full_text)}
    implied = sorted(IMPLIED_BY.get(s, set()) & have.keys())
    if implied:
        return {"skill": s, "credit": CREDIT_EXACT_LISTED, "status": "matched", "how": f"implied by {implied[0]}",
                "evidence": f"Has {', '.join(implied)}, which requires {s}"}
    sib = sorted(siblings(s) & have.keys())
    if sib:
        credit = CREDIT_EXACT_LISTED if or_similar else CREDIT_SIBLING
        return {"skill": s, "credit": credit, "status": "partial", "how": "similar skill", "via": sib,
                "evidence": f"Has {', '.join(sib)} (substitute for {s})"}
    best_sem, best_chunk = 0.0, None
    if sem_row is not None and len(sem_row):
        j = int(sem_row.argmax())
        best_sem, best_chunk = float(sem_row[j]), chunks[j]
    if best_sem >= SKILL_SEMANTIC_THRESHOLD:
        return {"skill": s, "credit": CREDIT_SEMANTIC, "status": "partial", "how": "semantically implied",
                "similarity": round(best_sem, 3), "evidence": best_chunk}
    return {"skill": s, "credit": 0.0, "status": "missing", "similarity": round(best_sem, 3),
            "closest_evidence": best_chunk if best_sem > 0.4 else None}


def _score_skill_list(jd_skills: list[str], resume: dict, chunks: list[str], weights: dict[str, float],
                      alternatives: list[list[str]] | None = None, or_similar: set[str] | None = None) -> dict:
    """Score coverage of a list of JD skills. Alternatives ("A or B") count as one item."""
    if not jd_skills:
        return {"score": None, "matched": [], "partial": [], "missing": []}
    have = {s["name"]: s for s in resume["skills"]}
    full_text = "\n".join(chunks) + "\n" + resume.get("skills_text", "")
    or_similar = or_similar or set()

    unresolved = [s for s in jd_skills if s not in have]
    sem = cosine_matrix([semantic_query(s) for s in unresolved], chunks) if unresolved and chunks else None

    items, seen = [], set()
    for s in jd_skills:
        if s in seen:
            continue
        group = next((g for g in alternatives or [] if s in g), [s])
        group = [g for g in group if g in jd_skills]
        seen.update(group)
        items.append(group)

    matched, partial, missing = [], [], []
    total_w = earned = 0.0
    for group in items:
        options = [_skill_credit(s, have, full_text, sem[unresolved.index(s)] if s in unresolved and sem is not None else None,
                                 chunks, s in or_similar) for s in group]
        best = max(options, key=lambda o: o["credit"])
        if len(group) > 1:
            best = {**best, "alternatives": group, "skill": " / ".join(group),
                    "satisfied_by": best["skill"] if best["status"] == "matched" else None}
        w = max(weights.get(s, 1.0) for s in group)
        total_w += w
        earned += w * best["credit"]
        {"matched": matched, "partial": partial, "missing": missing}[best["status"]].append(best)
    return {"score": earned / total_w, "matched": matched, "partial": partial, "missing": missing}



def _score_experience(jd: dict, resume: dict, jd_required: list[str]) -> dict:
    roles = resume.get("experience", [])
    jd_title = jd.get("title") or ""
    jd_skillset = set(jd_required)
    min_overlap = max(2, -(-len(jd_skillset) // 4))

    role_info = []
    if roles:
        titles = [r["title"] for r in roles]
        title_sims = cosine_matrix(titles, [jd_title])[:, 0] if jd_title else np.zeros(len(roles))
        role_texts = [f"{r['title']}. {r['description'][:400]}" for r in roles]
        req_profile = (jd_title + ". " + " ".join(jd.get("requirements", [])[:8]))[:1000]
        text_sims = cosine_matrix(role_texts, [req_profile])[:, 0]
        for r, ts, xs in zip(roles, title_sims, text_sims):
            role_skills = set(extract_skills(r["title"] + "\n" + r["description"]))
            overlap = sorted(role_skills & jd_skillset)
            relevance = max(float(ts), float(xs))
            relevant = ts >= ROLE_TITLE_THRESHOLD or xs >= ROLE_TEXT_THRESHOLD or len(overlap) >= min_overlap
            if float(ts) >= ROLE_TITLE_THRESHOLD:
                why = f"title similar to '{jd_title}' ({ts:.2f})"
            elif len(overlap) >= min_overlap:
                why = f"uses {len(overlap)} required skills: {', '.join(overlap[:4])}"
            elif relevant:
                why = f"responsibilities align with the JD ({xs:.2f})"
            else:
                why = "different domain from the JD"
            role_info.append({**{k: r[k] for k in ("title", "company", "start", "end", "months", "is_current")},
                              "relevant": bool(relevant), "relevance": round(relevance, 3), "why": why,
                              "skills_used": overlap})

    rel_int = [(date.fromisoformat(r["start"]), date.fromisoformat(r["end"])) for r in role_info if r["relevant"]]
    relevant_years = round(total_months(rel_int) / 12, 1)
    total_years = float(resume.get("total_years") or 0.0)
    if not roles:
        relevant_years = total_years
    min_y, max_y = jd.get("min_years"), jd.get("max_years")
    unrelated_credit = UNRELATED_EXPERIENCE_FACTOR * max(0.0, total_years - relevant_years)
    if min_y:
        unrelated_credit = min(unrelated_credit, UNRELATED_MAX_SHARE * min_y)
    effective = relevant_years + unrelated_credit

    if min_y:
        score = 1.0 if effective >= min_y else effective / min_y
        status = "meets" if effective >= min_y else ("close" if effective >= 0.75 * min_y else "below")
    else:
        score, status = None, "no requirement"
    return {
        "score": score, "status": status,
        "candidate_years": total_years, "relevant_years": relevant_years, "effective_years": round(effective, 1),
        "required_min": min_y, "required_max": max_y,
        "overqualified": bool(max_y and total_years > max_y + 3),
        "roles": role_info,
    }



def _score_semantic(jd: dict, chunks: list[str]) -> dict:
    reqs = jd.get("requirements", [])
    if not reqs or not chunks:
        return {"score": None if not reqs else 0.0, "pairs": []}
    sims = cosine_matrix(reqs, chunks)
    pairs = []
    for i, req in enumerate(reqs):
        j = int(sims[i].argmax())
        pairs.append({"requirement": req, "evidence": chunks[j], "similarity": round(float(sims[i, j]), 3),
                      "coverage": round(_calibrate(float(sims[i, j])), 3)})
    score = float(np.mean([p["coverage"] for p in pairs]))
    pairs.sort(key=lambda p: -p["similarity"])
    return {"score": score, "pairs": pairs}



def _score_education(jd: dict, resume: dict, effective_years: float) -> dict:
    req = jd.get("education") or {}
    need, fields = req.get("min_level", 0), req.get("accepted_fields") or req.get("fields", [])
    have = resume.get("highest_degree_level", 0)
    cand_fields = {e["field"] for e in resume.get("education", []) if e.get("field")}
    if not need and not fields:
        return {"score": None, "status": "no requirement", "candidate": resume.get("highest_degree"),
                "candidate_fields": sorted(cand_fields)}
    if have >= need:
        level_score, status = 1.0, "meets"
    elif have == need - 1 and have > 0:
        level_score, status = 0.5, "one level below"
    else:
        level_score, status = 0.0, "below"
    if level_score < 1 and req.get("equivalent_experience_ok") and effective_years >= (jd.get("min_years") or 3) + 2:
        level_score, status = max(level_score, 0.7), "equivalent experience"
    field_ok = (not fields) or bool(cand_fields & set(fields))
    score = 0.75 * level_score + 0.25 * (1.0 if field_ok else 0.3 if have else 0.0)
    return {"score": score, "status": status, "field_match": field_ok, "required_level": req.get("min_level_name"),
            "required_fields": req.get("fields", []), "related_fields_ok": req.get("related_fields_ok", False), "candidate": resume.get("highest_degree"), "candidate_fields": sorted(cand_fields)}



def verdict(score: float) -> str:
    if score >= 80:
        return "Strong match"
    if score >= 65:
        return "Good match"
    if score >= 50:
        return "Partial match"
    return "Weak match"


def score_candidate(jd: dict, resume: dict, weights: dict[str, float] | None = None) -> dict:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    chunks = resume.get("chunks", [])

    alts, similar = jd.get("alternatives", []), set(jd.get("or_similar", []))
    req = _score_skill_list(jd["required_skills"], resume, chunks, {}, alts, similar)
    pref_list = jd["preferred_skills"] + jd.get("soft_skills", [])
    pref_w = {s: 0.5 for s in jd.get("soft_skills", [])}
    pref = _score_skill_list(pref_list, resume, chunks, pref_w, alts, similar)
    exp = _score_experience(jd, resume, jd["required_skills"])
    sem = _score_semantic(jd, chunks)
    edu = _score_education(jd, resume, exp["effective_years"])

    comps = {"required_skills": req["score"], "experience": exp["score"], "semantic": sem["score"],
             "preferred_skills": pref["score"], "education": edu["score"]}
    active = {k: weights[k] for k, v in comps.items() if v is not None and weights.get(k, 0) > 0}
    wsum = sum(active.values()) or 1.0

    breakdown = []
    total = 0.0
    for k in DEFAULT_WEIGHTS:
        v = comps[k]
        if k in active:
            w = active[k] / wsum
            pts = w * v * 100
            total += pts
            breakdown.append({"key": k, "label": LABELS[k], "weight": round(w, 4), "score": round(v, 4),
                              "points": round(pts, 1), "max_points": round(w * 100, 1), "applied": True})
        else:
            breakdown.append({"key": k, "label": LABELS[k], "weight": 0, "score": None, "points": 0,
                              "max_points": 0, "applied": False})
    total = round(total, 1)

    extra = [s for s in resume.get("technical_skills", [])
             if s not in set(jd["required_skills"]) | set(jd["preferred_skills"])]

    result = {
        "score": total,
        "verdict": verdict(total),
        "breakdown": breakdown,
        "skills": {
            "required": jd["required_skills"],
            "required_count": len(req["matched"]) + len(req["partial"]) + len(req["missing"]),
            "matched": req["matched"], "partial": req["partial"], "missing": req["missing"],
            "preferred_matched": pref["matched"], "preferred_partial": pref["partial"],
            "preferred_missing": pref["missing"],
            "additional": extra[:25],
        },
        "experience": exp,
        "education": edu,
        "semantic": {"score": sem["score"], "top_matches": sem["pairs"][:5],
                     "gaps": [p for p in sem["pairs"] if p["coverage"] < 0.35][-5:]},
    }
    result["reasons"] = build_reasons(jd, result)
    return result



def _clip(text: str, n: int) -> str:
    """Shorten text to ~n characters on a word boundary."""
    if len(text) <= n:
        return text
    return text[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _fmt_years(y: float | None) -> str:
    if y is None:
        return "n/a"
    return f"{y:g} year" + ("" if y == 1 else "s")


def build_reasons(jd: dict, r: dict) -> list[dict]:
    """Human-readable, evidence-backed reasons. kind: positive | negative | neutral."""
    out: list[dict] = []
    sk = r["skills"]
    n_req = sk["required_count"]
    if n_req:
        names = [m["skill"] for m in sk["matched"]]
        kind = "positive" if len(names) >= 0.7 * n_req else "neutral" if len(names) >= 0.4 * n_req else "negative"
        out.append({"kind": kind, "area": "skills",
                    "text": f"Has {len(names)} of {n_req} required skills"
                            + (f": {', '.join(names[:8])}" if names else ".")})
        listed_only = [m["skill"] for m in sk["matched"] if m["how"] == "listed"]
        if listed_only:
            out.append({"kind": "neutral", "area": "skills",
                        "text": f"{', '.join(listed_only[:6])} listed but not shown in work experience "
                                f"(counted at {int(CREDIT_EXACT_LISTED * 100)}%)."})
        for p in sk["partial"]:
            if p["how"] == "similar skill":
                out.append({"kind": "neutral", "area": "skills",
                            "text": f"No {p['skill']}, but has {', '.join(p['via'])}, a close substitute (half credit)."})
            else:
                out.append({"kind": "neutral", "area": "skills",
                            "text": f"{p['skill']} not named, but implied by: “{_clip(p['evidence'], 110)}” "
                                    f"(similarity {p['similarity']:.2f}, half credit)."})
        if sk["missing"]:
            out.append({"kind": "negative", "area": "skills",
                        "text": f"Missing required skills: {', '.join(m['skill'] for m in sk['missing'])}."})
    if sk["preferred_matched"]:
        out.append({"kind": "positive", "area": "skills",
                    "text": f"Bonus skills: {', '.join(m['skill'] for m in sk['preferred_matched'][:6])}."})

    e = r["experience"]
    if e["required_min"]:
        req_txt = f"{e['required_min']:g}" + (f"–{e['required_max']:g}" if e["required_max"] else "+") + " years"
        txt = f"{_fmt_years(e['candidate_years'])} total experience, {_fmt_years(e['relevant_years'])} relevant"
        if e["effective_years"] != e["relevant_years"]:
            txt += (f" → {_fmt_years(e['effective_years'])} effective (unrelated years count a quarter, "
                    f"up to half the requirement)")
        txt += f"; JD asks for {req_txt}."
        kind = {"meets": "positive", "close": "neutral"}.get(e["status"], "negative")
        out.append({"kind": kind, "area": "experience", "text": txt})
    else:
        out.append({"kind": "neutral", "area": "experience",
                    "text": f"{_fmt_years(e['candidate_years'])} total, {_fmt_years(e['relevant_years'])} relevant; "
                            f"the JD does not state a years requirement."})
    if e["overqualified"]:
        out.append({"kind": "neutral", "area": "experience",
                    "text": f"Experience ({_fmt_years(e['candidate_years'])}) is well above the JD's range; "
                            f"may be overqualified (not penalised)."})
    unrelated = [x for x in e["roles"] if not x["relevant"]]
    if unrelated:
        out.append({"kind": "neutral", "area": "experience",
                    "text": f"{len(unrelated)} role(s) look unrelated to this job "
                            f"(e.g. {unrelated[0]['title']}); counted at a quarter weight."})

    sem = r["semantic"]
    if sem["score"] is not None:
        if sem["top_matches"]:
            best = sem["top_matches"][0]
            out.append({"kind": "positive" if best["coverage"] >= 0.6 else "neutral", "area": "semantic",
                        "text": f"Closest match to the JD requirement “{_clip(best['requirement'], 90)}” is: "
                                f"“{_clip(best['evidence'], 110)}” (similarity {best['similarity']:.2f})."})
        if sem["gaps"]:
            out.append({"kind": "negative", "area": "semantic",
                        "text": f"Little evidence for: “{_clip(sem['gaps'][-1]['requirement'], 110)}”."})

    ed = r["education"]
    if ed["score"] is not None:
        kind = "positive" if ed["score"] >= 0.9 else "neutral" if ed["score"] >= 0.5 else "negative"
        txt = f"Education: {ed['candidate'] or 'no degree found'}"
        if ed.get("candidate_fields"):
            txt += f" in {', '.join(ed['candidate_fields'])}"
        txt += f"; JD requires {ed.get('required_level') or 'a degree'}"
        if ed.get("required_fields"):
            txt += " in " + ", ".join(ed["required_fields"]) + (" or a related field" if ed.get("related_fields_ok") else "")
        txt += f" (level {ed['status']}" + ("" if ed.get("field_match", True) else ", field differs") + ")."
        out.append({"kind": kind, "area": "education", "text": txt})

    return out
