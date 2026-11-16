"""Degree / field-of-study detection shared by the resume and JD parsers."""

from __future__ import annotations

import re

LEVEL_NAMES = {1: "Diploma / Associate", 2: "Bachelor's", 3: "Master's", 4: "Doctorate"}

# Abbreviations are matched case-sensitively ("BE"/"MS" are also English words / "me" / "be").
_DEGREE_PATTERNS: list[tuple[int, re.Pattern]] = [
    (4, re.compile(r"\b(?:ph\.?\s?d|doctorate|doctor of philosophy)\b", re.I)),
    (3, re.compile(r"\b(?:master'?s?|post[\s-]?graduate)\b", re.I)),
    (3, re.compile(r"\b(?:M\.?Tech|M\.?S\.?|M\.S|M\.E\.|MBA|M\.?Sc|MCA|M\.?Eng|M\.A\.)(?![A-Za-z])(?!\s*(?:Excel|Office|SQL|Word|Teams|Azure|Project))")),
    (2, re.compile(r"\b(?:bachelor'?s?|undergraduate|graduate degree|engineering degree)\b", re.I)),
    (2, re.compile(r"\b(?:B\.?Tech|B\.?E\.|BE|B\.?S\.?|B\.?Sc|BCA|B\.?Eng|B\.?Com|B\.A\.|BBA)(?![A-Za-z])")),
    (1, re.compile(r"\b(?:diploma|associate'?s? degree)\b", re.I)),
]

FIELDS = {
    "Computer Science": ["computer science", "cse", "computer engineering", "computing", "computer applications", "computer systems"],
    "Information Technology": ["information technology", "information systems"],
    "Software Engineering": ["software engineering"],
    "Electronics / Electrical": ["electronics", "electrical", "ece", "eee", "telecommunication"],
    "Data Science / AI": ["data science", "artificial intelligence", "machine learning", "data analytics"],
    "Mathematics / Statistics": ["mathematics", "statistics", "applied math", "maths"],
    "Physics": ["physics"],
    "Mechanical Engineering": ["mechanical"],
    "Business": ["business administration", "commerce", "management", "finance", "economics"],
}

# Fields that a "Computer Science or related field" requirement should accept.
RELATED_TECH_FIELDS = {"Computer Science", "Information Technology", "Software Engineering",
                       "Electronics / Electrical", "Data Science / AI", "Mathematics / Statistics"}


def degree_level(text: str) -> int:
    """Highest degree level mentioned in a piece of text (0 = none)."""
    return max((lvl for lvl, pat in _DEGREE_PATTERNS if pat.search(text)), default=0)


def degree_levels(text: str) -> list[int]:
    return sorted({lvl for lvl, pat in _DEGREE_PATTERNS if pat.search(text)})


def fields_in(text: str) -> list[str]:
    low = text.lower()
    return [f for f, keys in FIELDS.items() if any(re.search(rf"\b{re.escape(k)}\b", low) for k in keys)]
