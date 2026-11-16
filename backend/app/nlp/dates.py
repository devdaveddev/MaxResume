"""Date-range detection and experience-duration arithmetic.

Supported forms (case-insensitive), any of -, –, —, to, until, till, → as separator:
    Mar 2019 – Present        March, 2019 - Current       Sept 2020 to now
    03/2019 - 06/2022         2019-03 – 2021-11           2018 – 2020
    Jan '19 – Feb '22         Summer 2019 - Fall 2020     Since March 2022  (open-ended)

Total experience is computed as the *union* of employment intervals, so two
overlapping jobs (e.g. a part-time role alongside a full-time one) are not
double counted.
"""

from __future__ import annotations

import re
from datetime import date

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9,
    "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
SEASONS = {"spring": 3, "summer": 6, "fall": 9, "autumn": 9, "winter": 12}

_MONTH = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
_SEASON = r"(?:spring|summer|fall|autumn|winter)"
_YEAR = r"(?:19|20)\d{2}"
_SHORT_YEAR = r"['’‘]\d{2}"
# A single date: "Mar 2019", "March, 2019", "Jan '19", "Summer 2019", "03/2019", "2019-03", "2019"
_DATE = (rf"(?:(?:{_MONTH}|{_SEASON})\s*,?\s*(?:{_YEAR}|{_SHORT_YEAR})"
         rf"|(?:0?[1-9]|1[0-2])\s*[/\-.]\s*{_YEAR}"
         rf"|{_YEAR}\s*[/\-]\s*(?:0?[1-9]|1[0-2])(?!\d)"
         rf"|{_YEAR})")
_PRESENT = r"(?:present|current(?:ly)?|now|till\s+date|to\s+date|ongoing|today|date)"
_SEP = r"\s*(?:-|–|—|−|to|until|till|→|>)\s*"

DATE_RANGE = re.compile(rf"(?P<start>{_DATE}){_SEP}(?P<end>{_DATE}|{_PRESENT})(?![\d/])", re.IGNORECASE)
# "Since March 2022", "From 2021 (ongoing)": open-ended ranges
OPEN_RANGE = re.compile(rf"\b(?:since|from)\s+(?P<start>{_DATE})(?!{_SEP}(?:{_DATE}|{_PRESENT}))", re.IGNORECASE)


def _year(token: str) -> int:
    token = token.strip("'’‘")
    y = int(token)
    if y < 100:  # '19 -> 2019, '98 -> 1998
        y += 2000 if y <= (date.today().year % 100) + 1 else 1900
    return y


def parse_date(s: str, is_end: bool = False, today: date | None = None) -> date | None:
    today = today or date.today()
    s = s.strip().lower().rstrip(".")
    if re.fullmatch(_PRESENT, s, re.IGNORECASE):
        return today
    m = re.match(rf"({_MONTH}|{_SEASON})\s*,?\s*({_YEAR}|{_SHORT_YEAR})", s, re.IGNORECASE)
    if m:
        key = m.group(1).rstrip(".")
        month = SEASONS.get(key) or MONTHS.get(key) or MONTHS[key[:3]]
        return date(_year(m.group(2)), month, 1)
    m = re.match(rf"(\d{{1,2}})\s*[/\-.]\s*({_YEAR})", s)
    if m:
        return date(int(m.group(2)), int(m.group(1)), 1)
    m = re.match(rf"({_YEAR})\s*[/\-]\s*(\d{{1,2}})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)
    m = re.match(rf"({_YEAR})", s)
    if m:
        # a bare year: assume January for a start date, December for an end date
        return date(int(m.group(1)), 12 if is_end else 1, 1)
    return None


def months_between(start: date, end: date) -> int:
    # inclusive of the start month: "Jan 2020 – Dec 2020" = 12 months
    return max(0, (end.year - start.year) * 12 + (end.month - start.month) + 1)


def merge_intervals(intervals: list[tuple[date, date]]) -> list[tuple[date, date]]:
    merged: list[tuple[date, date]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def total_months(intervals: list[tuple[date, date]]) -> int:
    return sum(months_between(s, e) for s, e in merge_intervals(intervals))


def gaps(intervals: list[tuple[date, date]], min_months: int = 6) -> list[tuple[date, date]]:
    """Periods of at least `min_months` between consecutive (merged) roles."""
    merged = merge_intervals(intervals)
    out = []
    for (_, end), (start, _) in zip(merged, merged[1:]):
        if months_between(end, start) - 2 >= min_months:
            out.append((end, start))
    return out


# "5+ years", "3-5 years", "minimum of 4 years", "at least 2 yrs", "8+ yrs"
YEARS_PATTERN = re.compile(
    r"(?P<min>\d{1,2}(?:\.\d)?)\s*(?:\+|plus)?\s*(?:(?:-|–|to)\s*(?P<max>\d{1,2})\s*\+?\s*)?(?:years?|yrs?)",
    re.IGNORECASE,
)
