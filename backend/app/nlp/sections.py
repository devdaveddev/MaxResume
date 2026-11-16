"""Split a document into named sections by detecting heading lines.

A line is treated as a heading when it is short and (after stripping
punctuation) matches one of the known heading phrases below, e.g.
"WORK EXPERIENCE", "Technical Skills:", "Education".
"""

from __future__ import annotations

import re

HEADINGS: dict[str, list[str]] = {
    # resume sections
    "summary": ["summary", "professional summary", "profile", "about me", "objective", "career objective",
                "career summary", "professional profile", "overview"],
    "skills": ["skills", "technical skills", "key skills", "core skills", "core competencies", "technologies",
               "tech stack", "skills & tools", "skills and tools", "tools & technologies", "areas of expertise",
               "competencies", "skill set", "technical proficiency"],
    "experience": ["experience", "work experience", "professional experience", "employment history",
                   "work history", "employment", "career history", "relevant experience"],
    "education": ["education", "academic background", "academics", "educational qualifications",
                  "education & training", "qualifications academic"],
    "projects": ["projects", "key projects", "personal projects", "academic projects", "selected projects"],
    "certifications": ["certifications", "certificates", "licenses & certifications", "certifications & training",
                       "courses", "training"],
    "achievements": ["achievements", "awards", "honors", "accomplishments", "awards & achievements"],
    "languages": ["languages", "spoken languages"],
    "interests": ["interests", "hobbies"],
    # job-description sections
    "jd_responsibilities": ["responsibilities", "key responsibilities", "what you will do", "what you'll do",
                            "role & responsibilities", "roles and responsibilities", "the role", "your role",
                            "job responsibilities", "duties"],
    "jd_required": ["requirements", "required skills", "required qualifications", "must have", "must-have",
                    "must haves", "minimum qualifications", "basic qualifications", "what we are looking for",
                    "what we're looking for", "who you are", "qualifications", "skills required",
                    "required", "you have", "requirements & qualifications", "key requirements"],
    "jd_preferred": ["preferred", "preferred skills", "preferred qualifications", "nice to have", "nice-to-have",
                     "good to have", "bonus points", "bonus", "pluses", "desired skills", "desirable",
                     "additional qualifications", "it would be great if"],
    "jd_about": ["about us", "about the company", "who we are", "company overview", "benefits", "perks",
                 "what we offer", "why join us", "compensation"],
}

_LOOKUP = {phrase: key for key, phrases in HEADINGS.items() for phrase in phrases}


def _heading_key(line: str) -> str | None:
    clean = re.sub(r"[^a-z&' \-]", "", line.lower()).strip(" -")
    clean = re.sub(r"\s+", " ", clean)
    if not clean or len(clean.split()) > 5 or len(line) > 50:
        return None
    if clean in _LOOKUP:
        return _LOOKUP[clean]
    # tolerate headings like "Experience Summary" / "Skills Summary"
    for phrase, key in _LOOKUP.items():
        if clean.startswith(phrase + " ") and len(clean.split()) <= len(phrase.split()) + 1:
            return key
    return None


def split_sections(text: str) -> dict[str, str]:
    """Returns {section_key: text}. Content before the first heading -> 'header'."""
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in text.split("\n"):
        stripped = line.strip()
        # "Skills: Java, Python" -> heading + inline content
        inline = None
        if ":" in stripped:
            head, _, rest = stripped.partition(":")
            if _heading_key(head) and rest.strip():
                inline = (_heading_key(head), rest.strip())
        if inline:
            sections.setdefault(inline[0], []).append(inline[1])
            # Resume "Skills: Java, SQL" opens the skills section, but a JD line such as
            # "Good to have: dbt, Snowflake" labels only itself; the lines after it belong
            # to the section they were already in.
            if not inline[0].startswith("jd_"):
                current = inline[0]
            continue
        key = _heading_key(stripped)
        if key:
            current = key
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}
