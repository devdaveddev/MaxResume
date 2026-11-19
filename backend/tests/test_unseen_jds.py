"""Job descriptions written in styles the parser was not developed against.

Each JD has a different shape: bulleted with "What we need:", inline "Must have: / Good to have:"
lines, and a single paragraph with no headings at all. The tests pin both the extraction and the
outcome a recruiter cares about: the right sample candidate ranks first.
"""

from pathlib import Path

import pytest

from app.ingest.extractors import extract
from app.matching.scorer import score_candidate
from app.nlp.resume_parser import parse_resume
from app.service import build_job

ROOT = Path(__file__).resolve().parents[2] / "sample_data"


def _jd(name):
    return build_job((ROOT / "job_descriptions" / name).read_text(), None)["parsed"]


@pytest.fixture(scope="module")
def profiles(samples):
    out = []
    for f in sorted((ROOT / "resumes").iterdir()):
        ex = extract(f.name, f.read_bytes())
        out.append(parse_resume(ex.text, f.name, links=ex.links))
    return out


def test_frontend_jd_bullets_and_slash_lists():
    p = _jd("frontend_engineer.txt")
    assert {"React", "TypeScript", "JavaScript", "Jest", "Figma", "Accessibility"} <= set(p["required_skills"])
    assert {"Next.js", "Storybook", "Cypress"} <= set(p["preferred_skills"])
    assert (p["min_years"], p["max_years"]) == (3, 6)
    assert p["education"]["min_level"] == 2


def test_inline_headings_label_only_their_own_line():
    p = _jd("data_analyst.txt")
    assert {"SQL", "Excel", "Power BI", "Tableau"} <= set(p["required_skills"])
    assert {"Python", "dbt", "Snowflake"} <= set(p["preferred_skills"])
    assert "Statistics" not in p["required_skills"] + p["preferred_skills"]
    assert p["min_years"] == 2 and p["education"]["min_level"] == 2
    assert any("dashboards" in s for s in p["requirements"])


def test_one_paragraph_jd_is_classified_sentence_by_sentence():
    p = _jd("site_reliability_engineer.txt")
    assert {"Kubernetes", "Terraform", "Helm", "ArgoCD", "Linux"} <= set(p["required_skills"])
    assert p["min_years"] == 4
    assert p["education"]["min_level"] == 0


@pytest.mark.parametrize("jd,winner", [
    ("frontend_engineer.txt", "Karan Desai"),
    ("site_reliability_engineer.txt", "Marcus Lee"),
    ("data_analyst.txt", "Tom Becker"),
])
def test_right_candidate_ranks_first(profiles, jd, winner):
    p = _jd(jd)
    ranked = sorted(profiles, key=lambda r: -score_candidate(p, r)["score"])
    assert ranked[0]["name"] == winner


def test_unrelated_experience_cannot_meet_the_requirement(profiles):
    p = _jd("frontend_engineer.txt")
    java_dev = next(r for r in profiles if r["name"] == "Sofia Ramirez")
    e = score_candidate(p, java_dev)["experience"]
    assert e["relevant_years"] == 0 and e["score"] <= 0.5
