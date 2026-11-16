"""Resume -> structured candidate profile.

Pipeline:
  1. split the text into sections (summary / skills / experience / education ...)
  2. contact details: emails (validated), phones (libphonenumber, normalised to
     E.164), profile links from text *and* embedded hyperlinks; name from the
     layout, spaCy NER, or the email address, with the source recorded
  3. skills via the taxonomy (with mention counts and where they were seen)
  4. work history: every date range (or "Since <date>") in the experience
     section starts a role; title/company are recovered from surrounding lines
  5. total experience = union of role intervals (overlaps not double counted),
     plus employment gaps
  6. education: degree level, field, institution, year, GPA
  7. "chunks": short sentences/bullets used later for semantic matching

Every extracted field that matters for trust has a `field_sources` entry, and
`parse_notes` lists anything suspicious, so quality checks (quality.py) can tell
the recruiter how much to rely on the parse.
"""

from __future__ import annotations

import re
from datetime import date
from functools import lru_cache
from pathlib import Path

import phonenumbers

from ..config import get_settings
from .dates import DATE_RANGE, OPEN_RANGE, YEARS_PATTERN, gaps, months_between, parse_date, total_months
from .education import LEVEL_NAMES, degree_level, fields_in
from .sections import HEADINGS, split_sections
from .skills import extract_skills
from .skills_taxonomy import SOFT_SKILL_CATEGORY, category_of

EMAIL = re.compile(r"(?<![\w.+-])[A-Za-z0-9][\w.+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,24}\b")
URL = re.compile(r"(?:https?://|www\.)[^\s|,;()<>\"']+|(?<![@\w])(?:linkedin\.com|github\.com|gitlab\.com)/[^\s|,;()<>\"']+",
                 re.I)
LINKEDIN = re.compile(r"linkedin\.com/(?:in|pub)/[\w%-]+", re.I)
GITHUB = re.compile(r"github\.com/[\w-]+", re.I)
INSTITUTION = re.compile(r"universit|institute|college|school|\biit\b|\bnit\b|academy|polytechnic|\bkth\b", re.I)
GPA = re.compile(r"\b(?:c?gpa|cpi)\s*[:\-]?\s*(\d{1,2}(?:\.\d{1,2})?)\s*(?:/\s*(\d{1,2}(?:\.\d)?))?", re.I)

ROLE_WORDS = re.compile(
    r"\b(engineer|developer|programmer|architect|manager|analyst|scientist|consultant|intern|lead|"
    r"designer|administrator|specialist|director|head|officer|associate|tester|qa|devops|sre|"
    r"technician|executive|trainee|researcher|founder|cto|vp|freelancer?|contractor)\b",
    re.I,
)
_HEADING_WORDS = {p for phrases in HEADINGS.values() for p in phrases}
_NOT_NAMES = {"curriculum vitae", "resume", "résumé", "cv", "contact", "profile", "personal details"}


@lru_cache(maxsize=1)
def _nlp():
    import spacy

    return spacy.load("en_core_web_sm", disable=["lemmatizer"])


# --------------------------------------------------------------------------- contact / name

def _name_from_email(email: str | None) -> str | None:
    if not email:
        return None
    local = email.split("@")[0]
    parts = [p for p in re.split(r"[._-]+", re.sub(r"\d+", "", local)) if len(p) > 1]
    return " ".join(p.capitalize() for p in parts) if 2 <= len(parts) <= 3 else None


def _extract_name(text: str, filename: str, email: str | None) -> tuple[str, str]:
    """Returns (name, source) with source in header | ner | email | filename."""
    for raw in [ln for ln in text.split("\n") if ln.strip()][:8]:
        line = re.split(r"\s[|•·,]\s|\s{3,}", raw.strip())[0].strip(" :")
        line = re.sub(r"^(?:name|candidate)\s*[:\-]\s*", "", line, flags=re.I)
        if not line or EMAIL.search(line) or re.search(r"\d|https?:|www\.|@", line):
            continue
        low = line.lower()
        if low in _NOT_NAMES or low in _HEADING_WORDS:
            continue
        words = line.split()
        if 2 <= len(words) <= 4 and all(re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ.'\-]*", w) for w in words):
            if not ROLE_WORDS.search(line) and not extract_skills(line):
                return " ".join(w.capitalize() if w.isupper() and len(w) > 2 else w for w in words), "header"
    for ent in _nlp()(text[:500]).ents:
        # small NER models happily tag "Spring Boot" as a person; reject anything that is a known skill
        if (ent.label_ == "PERSON" and 1 < len(ent.text.split()) <= 4 and not ROLE_WORDS.search(ent.text)
                and not extract_skills(ent.text)):
            return ent.text.strip(), "ner"
    from_email = _name_from_email(email)
    if from_email:
        return from_email, "email"
    stem = re.sub(r"[_\-]+|resume|cv|final|v\d+", " ", Path(filename).stem, flags=re.I).strip()
    return (stem.title() or "Unknown Candidate"), "filename"


def _extract_emails(text: str) -> list[str]:
    found = [e.lower().rstrip(".") for e in EMAIL.findall(text)]
    found = [e for e in found if not re.search(r"no-?reply|example\.(?:org|net)$|@domain\.|@email\.com$", e)]
    return list(dict.fromkeys(found))


def _extract_phones(text: str, region: str) -> list[dict]:
    """Valid phone numbers via libphonenumber, normalised (E.164 + international display)."""
    out, seen = [], set()
    head = text[:3000]
    for match in phonenumbers.PhoneNumberMatcher(head, region, leniency=phonenumbers.Leniency.VALID):
        e164 = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164)
        if e164 in seen:
            continue
        seen.add(e164)
        out.append({"e164": e164, "display": phonenumbers.format_number(
            match.number, phonenumbers.PhoneNumberFormat.INTERNATIONAL), "raw": match.raw_string})
    if out:
        return out
    # fallback for numbers libphonenumber rejects (e.g. fictional 555 ranges): keep a plausible digit run
    for m in re.finditer(r"(?:\+?\d{1,3}[\s.-]?)?\(?\d{2,5}\)?[\s.-]?\d{3,5}(?:[\s.-]?\d{3,5})?", head):
        digits = re.sub(r"\D", "", m.group())
        if 10 <= len(digits) <= 13 and not DATE_RANGE.search(m.group()):
            raw = m.group().strip()
            return [{"e164": ("+" if raw.startswith("+") else "") + digits, "display": raw, "raw": raw,
                     "unverified": True}]
    return []


def _classify_links(text: str, embedded: list[str]) -> dict:
    urls = [u.rstrip(".") for u in URL.findall(text)] + list(embedded or [])
    urls = [u for u in urls if not u.lower().startswith("mailto:")]
    linkedin = next((m.group() for u in urls for m in [LINKEDIN.search(u)] if m), None)
    github = next((m.group() for u in urls for m in [GITHUB.search(u)] if m), None)
    others = [u for u in dict.fromkeys(urls) if not LINKEDIN.search(u) and not GITHUB.search(u)]
    # the regexes capture "linkedin.com/in/x" without scheme; store canonical https URLs
    return {"linkedin": f"https://www.{linkedin}" if linkedin else None,
            "github": f"https://{github}" if github else None,
            "portfolio": others[:3]}


def _extract_location(header: str) -> str | None:
    m = re.search(r"(?:location|address|based in)\s*[:\-]?\s*([^\n|]+)", header, re.I)
    if m:
        return m.group(1).strip()[:80]
    for line in header.split("\n")[:8]:
        for seg in re.split(r"\s*[|•·]\s*|\s{3,}", line):
            seg = seg.strip()
            if (re.fullmatch(r"[A-Z][A-Za-z .'-]+,\s*[A-Z][A-Za-z .'-]+", seg)
                    and not ROLE_WORDS.search(seg) and len(seg.split()) <= 5 and "@" not in seg
                    and not extract_skills(seg)):
                return seg
    gpes = [e.text for e in _nlp()(header[:500]).ents if e.label_ == "GPE" and not extract_skills(e.text)]
    return ", ".join(dict.fromkeys(gpes[:2])) or None


# --------------------------------------------------------------------------- experience

_SPLIT = r"\s*[|•·]\s*|\s{2,}|\s[-–—]\s|,\s(?=[A-Z])"


def _split_title_company(parts: list[str]) -> tuple[str | None, str | None]:
    parts = [p.strip(" ,|-–—:") for p in parts if p and p.strip(" ,|-–—:")]
    parts = [p for p in parts if not re.fullmatch(r"(?:since|from)", p, re.I)]
    title = company = None
    for p in parts:
        if re.search(r"\s+at\s+", p, re.I) and not title:
            t, _, c = re.split(r"(\s+at\s+)", p, maxsplit=1, flags=re.I)
            return t.strip(), c.strip()
    for p in parts:
        if title is None and ROLE_WORDS.search(p) and len(p.split()) <= 7:
            title = p
        elif company is None and len(p.split()) <= 6 and not re.fullmatch(r"(remote|hybrid|onsite|on-site)", p, re.I):
            company = p
    return title, company


def _parse_experience(exp_text: str, today: date) -> tuple[list[dict], list[str]]:
    lines = exp_text.split("\n")
    notes: list[str] = []
    hits = []
    for i, line in enumerate(lines):
        m = DATE_RANGE.search(line)
        if m:
            hits.append((i, m, m.group("start"), m.group("end")))
            continue
        m = OPEN_RANGE.search(line)
        if m:
            hits.append((i, m, m.group("start"), "present"))

    roles, seen = [], set()
    for k, (i, m, start_s, end_s) in enumerate(hits):
        start, end = parse_date(start_s, today=today), parse_date(end_s, True, today)
        if not start or not end:
            continue
        if end < start:
            notes.append(f"Ignored a date range that ends before it starts: '{m.group(0)}'.")
            continue
        if start > today:
            notes.append(f"Ignored a role that starts in the future: '{m.group(0)}'.")
            continue
        if months_between(start, min(end, today)) > 50 * 12:
            notes.append(f"Ignored an implausible date range: '{m.group(0)}'.")
            continue
        end = min(end, today)
        # header pieces: the date line itself minus the date, the line above and the line below
        same_line = lines[i][: m.start()] + " | " + lines[i][m.end():]
        parts = re.split(_SPLIT, same_line)
        prev_end = hits[k - 1][0] if k else -1
        above = lines[i - 1].strip() if i - 1 > prev_end and i >= 1 else ""
        below = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if above and len(above.split()) <= 8 and not above.endswith("."):
            parts = re.split(_SPLIT, above) + parts
        used_below = False
        if below and len(below.split()) <= 7 and ROLE_WORDS.search(below) and not below.endswith("."):
            parts += [below]
            used_below = True
        title, company = _split_title_company(parts)

        next_i = hits[k + 1][0] if k + 1 < len(hits) else len(lines)
        desc_start = i + 2 if used_below else i + 1
        desc_end = next_i - 1 if (next_i < len(lines) and next_i - 1 > desc_start
                                   and len(lines[next_i - 1].split()) <= 8) else next_i
        description = "\n".join(ln for ln in lines[desc_start:desc_end] if ln.strip())
        key = ((title or "").lower(), (company or "").lower(), start)
        if key in seen:  # same role repeated (e.g. listed in summary and experience)
            continue
        seen.add(key)
        roles.append({
            "title": title or "Role",
            "company": company,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "is_current": bool(re.fullmatch(r"present|current(?:ly)?|now|till\s+date|to\s+date|ongoing|today|date",
                                            end_s.strip().lower())),
            "months": months_between(start, end),
            "date_text": m.group(0).strip(),
            "description": description[:1500],
        })
    if any(r["title"] == "Role" for r in roles):
        notes.append("Some roles have no recognisable job title.")
    return roles, notes


def _claimed_years(text: str) -> float | None:
    for m in YEARS_PATTERN.finditer(text[:3000]):
        window = text[m.end(): m.end() + 40].lower()
        if "experience" in window or "exp" in window:
            return float(m.group("min"))
    return None


# --------------------------------------------------------------------------- education

def _parse_education(edu_text: str) -> list[dict]:
    entries = []
    lines = [ln.strip() for ln in edu_text.split("\n") if ln.strip()]
    for i, line in enumerate(lines):
        lvl = degree_level(line)
        if not lvl:
            continue
        context = " ".join(lines[i: i + 3])
        inst = next((ln for ln in lines[i: i + 3] if INSTITUTION.search(ln)), None)
        years = [int(y) for y in re.findall(r"(?:19|20)\d{2}", context) if int(y) <= date.today().year + 6]
        gpa = GPA.search(context)
        # "M.Sc. in Software Engineering, KTH Royal Institute of Technology, 2019, GPA 3.8"
        parts = [p.strip() for p in re.split(r",\s+|\s[|–-]\s|\s{2,}", line) if p.strip()]
        degree = next((p for p in parts if degree_level(p)), parts[0])
        inst_part = next((p for p in parts if INSTITUTION.search(p)), None)
        if not inst_part and inst:
            inst_part = next((p.strip() for p in re.split(r",\s+|\s[|]\s", inst) if INSTITUTION.search(p)), inst)
        entries.append({
            "degree": degree[:120],
            "level": lvl,
            "level_name": LEVEL_NAMES[lvl],
            "field": (fields_in(context) or [None])[0],
            "institution": inst_part[:120] if inst_part else None,
            "year": years[-1] if years else None,
            "gpa": (f"{gpa.group(1)}/{gpa.group(2)}" if gpa and gpa.group(2) else gpa.group(1)) if gpa else None,
        })
    return entries


# --------------------------------------------------------------------------- chunks

def _unwrap(text: str) -> list[str]:
    """Re-join lines that a PDF wrapped mid-sentence.

    A line is continued when it does not end a sentence and the next line
    starts with a lowercase letter or digit ("...between\\nindependently deployable services").
    """
    out: list[str] = []
    for line in (ln.strip() for ln in text.split("\n")):
        if not line:
            continue
        if out and not re.search(r"[.;:!?]$", out[-1]) and re.match(r"[a-z0-9(]", line):
            out[-1] += " " + line
        else:
            out.append(line)
    return out


def make_chunks(text: str, max_chunks: int = 150) -> list[str]:
    """Split text into sentence/bullet-sized pieces for semantic comparison."""
    pieces = []
    for line in _unwrap(text):
        for sent in re.split(r"(?<=[.;!?])\s+(?=[A-Z])", line):
            sent = sent.strip(" .;")
            if len(sent.split()) >= 4:
                pieces.append(sent[:300])
    return list(dict.fromkeys(pieces))[:max_chunks]


# --------------------------------------------------------------------------- main entry

def parse_resume(text: str, filename: str, today: date | None = None, links: list[str] | None = None) -> dict:
    today = today or date.today()
    settings = get_settings()
    sections = split_sections(text)
    header = sections.get("header", text[:600])
    notes: list[str] = []

    # --- contact
    emails = _extract_emails(text)
    phones = _extract_phones(text, settings.default_phone_region)
    name, name_source = _extract_name(text, filename, emails[0] if emails else None)
    link_info = _classify_links(text, links or [])

    # --- skills: count mentions, remember whether they were listed explicitly
    #     in a skills section and/or backed by usage in experience/projects
    # (education is excluded: "Electronics and Communication" is a degree, not a soft skill)
    skill_text = "\n".join(v for k, v in sections.items() if k != "education")
    counts = extract_skills(skill_text)
    in_skill_section = set(extract_skills(sections.get("skills", "")))
    applied_text = "\n".join(sections.get(s, "") for s in ("experience", "projects"))
    in_experience = set(extract_skills(applied_text))
    skills = [
        {"name": s, "category": category_of(s), "mentions": n,
         "listed": s in in_skill_section, "used_in_experience": s in in_experience}
        for s, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    # --- experience
    exp_text = sections.get("experience")
    if not exp_text:  # no heading found: scan everything except education/certifications/projects
        exp_text = "\n".join(v for k, v in sections.items() if k not in {"education", "certifications", "projects"})
        notes.append("No experience section heading found; roles were detected from the whole document.")
    roles, exp_notes = _parse_experience(exp_text, today)
    notes += exp_notes
    roles.sort(key=lambda r: (r["end"], r["start"]), reverse=True)  # most recent first
    intervals = [(date.fromisoformat(r["start"]), date.fromisoformat(r["end"])) for r in roles]
    computed_years = round(total_months(intervals) / 12, 1) if roles else None
    claimed = _claimed_years(sections.get("summary", "") + "\n" + header)
    total_years = computed_years if computed_years is not None else (claimed or 0.0)
    gap_list = [{"from": a.isoformat(), "to": b.isoformat(), "months": months_between(a, b) - 2}
                for a, b in gaps(intervals)]
    overlap_months = sum(r["months"] for r in roles) - total_months(intervals)

    # --- education
    edu_text = sections.get("education") or text
    education = _parse_education(edu_text)
    highest = max((e["level"] for e in education), default=0)

    certifications = [ln.strip() for ln in sections.get("certifications", "").split("\n") if len(ln.split()) >= 2][:15]
    summary = sections.get("summary") or ""
    current = next((r for r in roles if r["is_current"]), roles[0] if roles else None)

    return {
        "name": name,
        "email": emails[0] if emails else None,
        "emails": emails,
        "phone": phones[0]["display"] if phones else None,
        "phone_e164": phones[0]["e164"] if phones else None,
        "phones": phones,
        "linkedin": link_info["linkedin"],
        "github": link_info["github"],
        "portfolio": link_info["portfolio"],
        "location": _extract_location(header),
        "current_title": current["title"] if current else None,
        "current_company": current["company"] if current else None,
        "summary": summary[:800],
        "skills": skills,
        "technical_skills": [s["name"] for s in skills if s["category"] != SOFT_SKILL_CATEGORY],
        "soft_skills": [s["name"] for s in skills if s["category"] == SOFT_SKILL_CATEGORY],
        "experience": roles,
        "total_years": total_years,
        "computed_years": computed_years,
        "claimed_years": claimed,
        "employment_gaps": gap_list,
        "overlap_months": max(0, overlap_months),
        "education": education,
        "highest_degree_level": highest,
        "highest_degree": LEVEL_NAMES.get(highest),
        "certifications": certifications,
        "sections_found": [k for k in sections if k != "header"],
        "word_count": len(text.split()),
        "field_sources": {"name": name_source,
                          "phone": "unverified" if phones and phones[0].get("unverified") else ("libphonenumber" if phones else None),
                          "experience": "dated roles" if roles else ("claimed in text" if claimed else None)},
        "parse_notes": notes,
        "skills_text": sections.get("skills", "")[:2000],
        # Semantic evidence comes from what the candidate *did* (summary,
        # experience, projects ...), not from the bare skills list, which is
        # already scored by the skills component.
        "chunks": make_chunks("\n".join(v for k, v in sections.items() if k != "skills")),
    }
