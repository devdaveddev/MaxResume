"""Field-level resume parsing accuracy against known ground truth.

Ground truth comes from the data the synthetic resumes were generated from
(scripts/generate_samples.py, scripts/generate_edge_cases.py), so every expected
value is exact, not hand-labelled guesswork.

Checked per resume:
  name, email, phone (digits), location, LinkedIn,
  number of roles, and per role: title, company, start month, end month / "current",
  total years (±0.15 of the value computed from the true dates),
  education: degree level, institution, year,
  skills: recall of the skills the resume lists (taxonomy vocabulary only),
          and precision (no skill reported that is not in the document).

Run:  uv run python scripts/eval_parsing.py         (prints a report)
      uv run python scripts/eval_parsing.py --json  (machine-readable)

Caveat: these resumes are synthetic and the parser was developed against them,
so this measures correctness on known layouts (a regression baseline), not
accuracy on arbitrary real-world resumes.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.ingest.detect import FileRejected  # noqa: E402
from app.ingest.extractors import extract  # noqa: E402
from app.nlp.dates import total_months  # noqa: E402
from app.nlp.resume_parser import parse_resume  # noqa: E402
from app.nlp.skills_taxonomy import SKILLS  # noqa: E402
from generate_heldout import OUT as HELDOUT_DIR  # noqa: E402
from generate_heldout import TRUTH as HELDOUT_TRUTH  # noqa: E402
from generate_samples import CANDIDATES  # noqa: E402

TODAY = date.today()
_ALIAS = {a.lower(): canon for canon, meta in SKILLS.items() for a in meta["aliases"]}


def _month(s: str) -> str | None:
    return None if s.lower() == "present" else datetime.strptime(s, "%b %Y").strftime("%Y-%m")


def _level(degree: str) -> int:
    d = degree.lower()
    return 3 if d.startswith(("m.", "m ", "ms", "master", "mtech", "msc", "m.sc")) else 2


def _skills(listed: str) -> set[str]:
    return {_ALIAS[s.strip().lower()] for s in listed.split(",") if s.strip().lower() in _ALIAS}


def sample_truth() -> list[dict]:
    out = []
    for c in CANDIDATES:
        out.append({
            "file": ROOT / "sample_data" / "resumes" / c["file"],
            "name": c["name"], "email": c["email"], "phone": re.sub(r"\D", "", c["phone"]),
            "location": c["location"], "linkedin": (c.get("linkedin") or "").split("/")[-1] or None,
            "roles": [(t, co, _month(s), _month(e)) for t, co, _city, s, e, _b in c["roles"]],
            "education": [(_level(d), inst, int(y)) for d, inst, y in c["education"]],
            "skills": _skills(c["skills"]),
        })
    return out


def edge_truth() -> list[dict]:
    e = ROOT / "sample_data" / "edge_cases"
    jonas = {"name": "Jonas Lindqvist", "email": "jonas.lindqvist@example.com", "phone": "46555123456",
             "location": "Stockholm, Sweden", "linkedin": "jonas-lindqvist-demo",
             "roles": [("Backend Developer", "Nordbyte AB", "2019-04", None)],
             "education": [(3, "KTH Royal Institute of Technology", 2019)],
             "skills": {"Java", "Spring Boot", "PostgreSQL", "Docker", "Git"}}
    return [
        {"file": e / "two_column.pdf", "name": "Amara Okonkwo", "email": "amara.okonkwo@example.com",
         "phone": "445550182331", "location": "Leeds, UK", "linkedin": "amara-okonkwo-demo",
         "roles": [("Senior Backend Engineer", "Ledgerline", "2021-02", None),
                   ("Backend Engineer", "Quayside Tech", "2016-09", "2021-01")],
         "education": [(2, "University of Leeds", 2016)],
         "skills": {"Java", "Spring Boot", "Kafka", "PostgreSQL", "Docker", "Kubernetes", "AWS"}},
        {"file": e / "scanned.pdf", "name": "Ravi Shankar", "email": "ravi.shankar@example.com",
         "phone": "919845055507", "location": "Pune, India", "linkedin": None,
         "roles": [("Senior Java Developer", "Tidal Systems", "2020-03", None),
                   ("Java Developer", "Nimbus Soft", "2017-06", "2020-02")],
         "education": [(2, "Pune University", 2017)],
         "skills": {"Java", "Spring Boot", "Kafka", "PostgreSQL", "Docker", "Kubernetes", "AWS"}},
        {"file": e / "tricky_dates.txt", "name": "Elena Petrova", "email": "elena.petrova@example.com",
         "phone": "5550142233", "location": "Denver, CO", "linkedin": None,
         "roles": [("Staff Engineer", "Quartz Labs", "2022-03", None),
                   ("Senior Engineer", "Bluebird Analytics", "2019-01", "2022-02"),
                   ("Freelance Consultant", None, "2019-01", "2020-12"),
                   ("Software Engineer", "Copperline", "2015-06", "2017-08")],
         "education": [(3, "University of Colorado", 2015)],
         "skills": {"Kubernetes", "Terraform", "Go", "Python", "Spark", "AWS", "Java", "PostgreSQL"}},
        *[{"file": e / n, **jonas} for n in ("header_contact.docx", "legacy.doc", "resume.rtf", "resume.odt")],
    ]


def heldout_truth(group: str) -> list[dict]:
    """Resumes in layouts the parser was not developed against (see generate_heldout.py).
    group 'dev' found bugs that were then fixed; group 'heldout' was never used for tuning."""
    return [{"file": HELDOUT_DIR / name, "name": t["name"], "email": t["email"], "phone": t["phone"],
             "location": t["location"], "linkedin": None, "roles": t["roles"], "education": t["education"],
             "skills": t["skills"]}
            for name, t in HELDOUT_TRUTH.items() if t["group"] == group]


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def evaluate(truths: list[dict]) -> dict:
    fields: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    skill_tp = skill_fn = skill_fp = 0
    failures: list[str] = []
    skipped: list[str] = []

    def check(field: str, ok: bool, label: str, got, want):
        fields[field][1] += 1
        if ok:
            fields[field][0] += 1
        else:
            failures.append(f"{label}: {field} got {got!r}, expected {want!r}")

    for t in truths:
        f: Path = t["file"]
        if not f.exists():
            continue
        try:
            ex = extract(f.name, f.read_bytes())
        except FileRejected as e:
            if e.code == "unsupported":
                skipped.append(f"{f.name}: {e}")
                continue
            raise
        p = parse_resume(ex.text, f.name, today=TODAY, links=ex.links)
        lab = f.name

        check("name", p["name"] == t["name"], lab, p["name"], t["name"])
        check("email", p["email"] == t["email"], lab, p["email"], t["email"])
        got_phone = re.sub(r"\D", "", p.get("phone_e164") or p.get("phone") or "")
        check("phone", got_phone.endswith(t["phone"][-10:]), lab, got_phone, t["phone"])
        loc = _norm(p["location"])
        check("location", loc == _norm(t["location"]) or loc.startswith(_norm(t["location"]).split(",")[0] + ","),
              lab, p["location"], t["location"])
        if t["linkedin"]:
            check("linkedin", bool(p["linkedin"]) and t["linkedin"] in p["linkedin"], lab, p["linkedin"], t["linkedin"])

        want_roles = sorted(t["roles"], key=lambda r: r[2], reverse=True)
        got_roles = sorted(p["experience"], key=lambda r: r["start"], reverse=True)
        check("role_count", len(got_roles) == len(want_roles), lab, len(got_roles), len(want_roles))
        for (title, company, start, end), g in zip(want_roles, got_roles):
            check("role_title", _norm(g["title"]) == _norm(title), lab, g["title"], title)
            check("role_company", (company is None and not g["company"]) or
                  (company is not None and _norm(g["company"]).startswith(_norm(company))), lab, g["company"], company)
            check("role_start", g["start"][:7] == start, lab, g["start"][:7], start)
            ok_end = g["is_current"] if end is None else (g["end"][:7] == end and not g["is_current"])
            check("role_end", ok_end, lab, "current" if g["is_current"] else g["end"][:7], end or "current")

        def to_date(m, is_end=False):
            return TODAY if m is None else date(int(m[:4]), int(m[5:7]), 1)
        true_years = round(total_months([(to_date(s), min(to_date(e, True), TODAY)) for _, _, s, e in t["roles"]]) / 12, 1)
        check("total_years", abs(p["total_years"] - true_years) <= 0.15, lab, p["total_years"], true_years)

        for (lvl, inst, yr), g in zip(t["education"], p["education"]):
            check("degree_level", g["level"] == lvl, lab, g["level"], lvl)
            check("institution", _norm(g["institution"]).startswith(_norm(inst)[:20]), lab, g["institution"], inst)
            check("grad_year", g["year"] == yr, lab, g["year"], yr)
        if len(p["education"]) < len(t["education"]):
            check("degree_level", False, lab, len(p["education"]), len(t["education"]))

        got = set(p["skills"] and [s["name"] for s in p["skills"]])
        tp = len(got & t["skills"])
        skill_tp += tp
        skill_fn += len(t["skills"] - got)
        text = ex.text.lower()
        for s in got:
            if not any(re.search(r"(?<![a-z0-9])" + re.escape(a.lower()) + r"(?![a-z0-9])", text)
                       for a in SKILLS[s]["aliases"]):
                skill_fp += 1
                failures.append(f"{lab}: skill {s!r} reported but not in text")
        for s in t["skills"] - got:
            failures.append(f"{lab}: skill {s!r} missed")

    per_field = {k: {"correct": c, "total": n, "accuracy": round(c / n, 4)} for k, (c, n) in sorted(fields.items())}
    correct = sum(c for c, _ in fields.values())
    total = sum(n for _, n in fields.values())
    recall = skill_tp / max(1, skill_tp + skill_fn)
    precision = skill_tp / max(1, skill_tp + skill_fp)
    return {
        "resumes": len([t for t in truths if t["file"].exists()]) - len(skipped),
        "skipped": skipped,
        "field_checks": total,
        "field_accuracy": round(correct / max(1, total), 4),
        "per_field": per_field,
        "skills": {"recall": round(recall, 4), "precision": round(precision, 4),
                   "f1": round(2 * recall * precision / max(1e-9, recall + precision), 4)},
        "failures": failures,
    }


def main() -> None:
    groups = {"samples (14)": sample_truth(), "edge cases (7)": edge_truth(),
              "unseen layouts, dev (4): found bugs, now fixed": heldout_truth("dev"),
              "unseen layouts, held-out (3): first run 92.2%, then '@' fixed": heldout_truth("heldout")}
    results = {g: evaluate(t) for g, t in groups.items()}
    results["overall"] = evaluate(sample_truth() + edge_truth() + heldout_truth("dev") + heldout_truth("heldout"))
    if "--json" in sys.argv:
        print(json.dumps(results, indent=2))
        return
    for g, r in results.items():
        print(f"\n=== {g}: {r['resumes']} resumes, {r['field_checks']} field checks"
              + (f" ({len(r['skipped'])} skipped: format not supported on this machine)" if r["skipped"] else ""))
        print(f"field accuracy {r['field_accuracy']:.1%} | skills recall {r['skills']['recall']:.1%} "
              f"precision {r['skills']['precision']:.1%} F1 {r['skills']['f1']:.1%}")
        if r["failures"] and "held-out" in g:
            print("  held-out failures:")
            for f in r["failures"]:
                print("   -", f)
        if g == "overall":
            for k, v in r["per_field"].items():
                print(f"  {k:14} {v['correct']:3}/{v['total']:<3} {v['accuracy']:.1%}")
            print("failures:" if r["failures"] else "failures: none")
            for f in r["failures"]:
                print("  -", f)


if __name__ == "__main__":
    main()
