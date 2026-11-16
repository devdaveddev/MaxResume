"""Dictionary-based skill extraction (exact + alias matching).

This is the *precise* half of skill matching. The *semantic* half (finding
skills that are implied but not literally named) lives in matching/scorer.py.
"""

from __future__ import annotations

import re
from functools import lru_cache

from .skills_taxonomy import CASE_SENSITIVE_ALIASES, SKILLS

# Characters that can be part of a skill token: "C++", "C#", ".NET", "Node.js", "CI/CD"
# "/" is a separator ("JavaScript/TypeScript", "REST/GraphQL"); aliases that contain one
# ("CI/CD", "PL/SQL") still match whole because longer aliases claim their span first.
_LEFT = r"(?<![A-Za-z0-9+#.\-])"
_RIGHT = r"(?![A-Za-z0-9+#]|\.[A-Za-z0-9])"


@lru_cache(maxsize=1)
def _patterns() -> list[tuple[str, re.Pattern]]:
    pats = []  # (canonical, pattern, alias_length)
    for canonical, meta in SKILLS.items():
        for alias in meta["aliases"]:
            body = re.escape(alias).replace(r"\ ", r"[\s\-]+")
            if alias in CASE_SENSITIVE_ALIASES:
                # also reject "Spring 2021" / "C 2019" style false positives (semesters, grades)
                pats.append((canonical, re.compile(_LEFT + body + _RIGHT + r"(?!\s+\d{4})"), len(alias)))
            else:
                pats.append((canonical, re.compile(_LEFT + body + _RIGHT, re.IGNORECASE), len(alias)))
    # longer aliases first so "spring boot" claims its span before "spring"
    pats.sort(key=lambda p: -p[2])
    return [(c, pat) for c, pat, _ in pats]


def find_skill_spans(text: str) -> list[tuple[int, int, str]]:
    """All non-overlapping skill mentions as (start, end, canonical), in text order.

    Patterns are tried longest-first and a span, once claimed, cannot be reused,
    so "Spring Boot" does not also count as "Spring", and "SQL Server" does not
    also count as "SQL".
    """
    taken = bytearray(len(text))
    spans = []
    for canonical, pat in _patterns():
        for m in pat.finditer(text):
            if any(taken[m.start():m.end()]):
                continue
            taken[m.start():m.end()] = b"\x01" * (m.end() - m.start())
            spans.append((m.start(), m.end(), canonical))
    return sorted(spans)


def extract_skills(text: str) -> dict[str, int]:
    """Return {canonical_skill: number_of_mentions} found in text."""
    counts: dict[str, int] = {}
    for _, _, canonical in find_skill_spans(text):
        counts[canonical] = counts.get(canonical, 0) + 1
    return counts


_OR_BETWEEN = re.compile(r"^\s*(?:,\s*)?(?:or|/|or\s+an?)\s*$", re.I)
_OR_SIMILAR = re.compile(r"^\s*(?:or|and/or)\s+(?:similar|equivalent|other|comparable|related)", re.I)


def extract_alternatives(text: str) -> tuple[list[list[str]], set[str]]:
    """Detect "Jenkins or GitHub Actions" style alternatives and "Kafka or similar".

    Returns (groups, or_similar):
      groups      – lists of skills where any one satisfies the requirement
      or_similar  – skills followed by "or similar/equivalent", for which a
                    substitute from the same family earns full credit
    """
    groups: list[list[str]] = []
    or_similar: set[str] = set()
    for line in text.split("\n"):
        spans = find_skill_spans(line)
        current: list[str] = []
        for i, (_start, e, skill) in enumerate(spans):
            if _OR_SIMILAR.match(line[e:e + 40]):
                or_similar.add(skill)
            nxt = spans[i + 1] if i + 1 < len(spans) else None
            if nxt and _OR_BETWEEN.match(line[e:nxt[0]]):
                current = current or [skill]
                current.append(nxt[2])
            elif current:
                groups.append(list(dict.fromkeys(current)))
                current = []
        if current:
            groups.append(list(dict.fromkeys(current)))
    return [g for g in groups if len(g) > 1], or_similar


def find_skill_context(skill: str, text: str, width: int = 90) -> str | None:
    """Return a short snippet of text around the first mention of a skill (for explanations)."""
    for canonical, pat in _patterns():
        if canonical != skill:
            continue
        m = pat.search(text)
        if m:
            start, end = max(0, m.start() - width // 2), min(len(text), m.end() + width // 2)
            snippet = text[start:end].replace("\n", " ").strip()
            return ("…" if start > 0 else "") + snippet + ("…" if end < len(text) else "")
    return None
