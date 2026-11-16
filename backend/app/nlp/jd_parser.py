"""Job description -> structured requirements.

Output fields:
  title, required_skills, preferred_skills, min_years, max_years,
  education {min_level, fields, equivalent_experience_ok},
  requirements (list of requirement/responsibility statements used for
  semantic matching), soft_skills.

Required vs preferred is decided in two layers:
  1. section headings ("Requirements" vs "Nice to have");
  2. line-level cues inside any section ("... is a plus", "preferred",
     "familiarity with") which demote that line to preferred.
"""

from __future__ import annotations

import re

from .dates import YEARS_PATTERN
from .education import LEVEL_NAMES, RELATED_TECH_FIELDS, degree_levels, fields_in
from .sections import split_sections
from .skills import extract_alternatives, extract_skills
from .skills_taxonomy import SOFT_SKILL_CATEGORY, category_of

PREFERRED_CUES = re.compile(
    r"\b(preferred|preferably|nice[\s-]to[\s-]have|good[\s-]to[\s-]have|a plus|is a plus|are a plus|bonus|"
    r"desirable|an advantage|added advantage|would be great|familiarity with|exposure to|optional)\b",
    re.I,
)
METADATA_LINE = re.compile(r"^(?:location|job\s*type|employment\s*type|salary|ctc|department|team|"
                           r"reports\s*to|work\s*mode|start\s*date|posted|job\s*id|title|position|role)\s*[:\-]", re.I)
TITLE_PATTERN = re.compile(r"^(?:job\s*title|position|role|title|designation)\s*[:\-]\s*(.+)$", re.I | re.M)


def _detect_title(text: str) -> str | None:
    m = TITLE_PATTERN.search(text)
    if m:
        return m.group(1).strip()[:100]
    for line in text.split("\n")[:5]:
        line = line.strip(" #*")
        if line and len(line.split()) <= 8 and not line.endswith(".") and ":" not in line:
            return line[:100]
    return None


def _years(lines: list[str]) -> tuple[float | None, float | None]:
    """Minimum (and optional maximum) years of experience requested."""
    best: tuple[float | None, float | None] = (None, None)
    for line in lines:
        for m in YEARS_PATTERN.finditer(line):
            after = line[m.end(): m.end() + 60].lower()
            before = line[max(0, m.start() - 40): m.start()].lower()
            # Requirement lines phrase it many ways ("5+ years of experience", "3-6 years building web
            # apps", "4+ years in SRE"); skip numbers about the company, warranties or vesting.
            if re.search(r"founded|in business|\bold\b|\bago\b|warranty|vesting|history|track record", before + after):
                continue
            lo = float(m.group("min"))
            if lo:
                hi = float(m.group("max")) if m.group("max") else None
                # prefer the most demanding overall requirement (e.g. "5+ years" over "2 years of Kafka")
                if best[0] is None or lo > best[0]:
                    best = (lo, hi)
    return best


def parse_jd(text: str, title: str | None = None) -> dict:
    sections = split_sections(text)
    required_lines: list[str] = []
    preferred_lines: list[str] = []
    responsibility_lines: list[str] = []

    detected_title = _detect_title(text)
    for key, body in sections.items():
        if key == "jd_about" or key in {"interests", "languages"}:
            continue  # company blurb / benefits: no candidate requirements in here
        for line in (ln.strip() for ln in body.split("\n")):
            if not line or (key == "header" and (line == detected_title or METADATA_LINE.match(line))):
                continue  # title / "Location: ..." / "Job type: ..." are not requirements
            # Classify sentence by sentence: in a one-paragraph JD, "Bachelor's degree preferred"
            # must not turn every other requirement in the paragraph into a nice-to-have.
            for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", line):
                sentence = sentence.strip()
                if not sentence:
                    continue
                if key == "jd_preferred" or PREFERRED_CUES.search(sentence):
                    preferred_lines.append(sentence)
                else:
                    required_lines.append(sentence)
                    if key == "jd_responsibilities":
                        responsibility_lines.append(sentence)

    # Degree lines name fields of study ("Statistics, Economics"), not skills.
    def skill_source(lines: list[str]) -> str:
        return "\n".join(ln for ln in lines if not (degree_levels(ln) or re.search(r"\bdegree\b", ln, re.I)))

    req_counts = extract_skills(skill_source(required_lines))
    pref_counts = extract_skills(skill_source(preferred_lines))
    required = [s for s in req_counts]
    preferred = [s for s in pref_counts if s not in req_counts]

    # Soft skills are kept separately; they get a small weight in scoring.
    soft = [s for s in required + preferred if category_of(s) == SOFT_SKILL_CATEGORY]
    required = [s for s in required if s not in soft]
    preferred = [s for s in preferred if s not in soft]

    # "Jenkins or GitHub Actions" -> one requirement satisfied by either skill
    groups, or_similar = extract_alternatives("\n".join(required_lines + preferred_lines))
    alternatives = [g for g in groups if set(g) <= set(required) or set(g) <= set(preferred)]

    min_years, max_years = _years(required_lines + preferred_lines)

    # Education: lowest degree level mentioned in the requirements is the bar
    # ("Bachelor's or Master's in CS" -> Bachelor's is enough).
    edu_lines = [ln for ln in required_lines if degree_levels(ln) or re.search(r"\bdegree\b", ln, re.I)]
    levels = [lvl for ln in edu_lines for lvl in degree_levels(ln)]
    min_level = min(levels) if levels else (2 if edu_lines else 0)
    fields = sorted({f for ln in edu_lines for f in fields_in(ln)})
    related_ok = any(re.search(r"related field|related discipline|equivalent", ln, re.I) for ln in edu_lines)
    accepted = set(fields)
    if related_ok and set(fields) & RELATED_TECH_FIELDS:
        accepted |= RELATED_TECH_FIELDS  # "CS or a related field" accepts other technical degrees
    equivalent_ok = any(re.search(r"equivalent (practical |work )?experience", ln, re.I) for ln in edu_lines)

    # Requirement statements for semantic matching (full sentences carry
    # context that bare skill names do not, e.g. "design high-throughput APIs").
    # Years and degree lines are scored by their own components, so they are
    # excluded here to avoid counting the same requirement twice.
    statements = [ln for ln in dict.fromkeys(responsibility_lines + required_lines)
                  if len(ln.split()) >= 4 and ln not in edu_lines and not YEARS_PATTERN.search(ln)]

    return {
        "title": title or detected_title or "Untitled role",
        "required_skills": required,
        "preferred_skills": preferred,
        "soft_skills": soft,
        "alternatives": alternatives,
        "or_similar": sorted(or_similar),
        "min_years": min_years,
        "max_years": max_years,
        "education": {
            "min_level": min_level,
            "min_level_name": LEVEL_NAMES.get(min_level),
            "fields": fields,
            "accepted_fields": sorted(accepted),
            "related_fields_ok": related_ok,
            "equivalent_experience_ok": equivalent_ok,
        },
        "requirements": statements[:40],
        "preferred_requirements": [ln for ln in preferred_lines if len(ln.split()) >= 4][:20],
        "sections_found": [k for k in sections if k != "header"],
    }
