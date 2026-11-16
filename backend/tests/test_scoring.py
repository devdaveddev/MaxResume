import copy

from app.matching.scorer import score_candidate
from app.nlp.jd_parser import parse_jd
from app.nlp.resume_parser import parse_resume
from app.nlp.text_extract import extract_text

JD_TEXT = """Backend Engineer
Requirements
4+ years of experience building backend services.
Strong Java and Spring Boot skills.
Experience with PostgreSQL and Kafka.
Bachelor's degree in Computer Science.
Nice to have
Redis is a plus.
"""


def _resume(text):
    return parse_resume(text, "r.txt")


STRONG = """Alex Example
alex@example.com
Skills: Java, Spring Boot, PostgreSQL, Kafka, Redis
Experience
Senior Backend Engineer | Acme | Jan 2019 – Present
Built Java Spring Boot services backed by PostgreSQL and Kafka event streams, with Redis caching.
Education
B.Tech in Computer Science, Some University, 2018
"""

WEAK = """Sam Example
sam@example.com
Skills: Photoshop, Illustrator
Experience
Graphic Designer | Studio | Jan 2023 – Present
Designed brand identities and marketing posters.
Education
B.A. in Fine Arts, Art College, 2022
"""


def test_score_range_and_order():
    jd = parse_jd(JD_TEXT)
    s, w = score_candidate(jd, _resume(STRONG)), score_candidate(jd, _resume(WEAK))
    assert 0 <= w["score"] < s["score"] <= 100
    assert s["score"] >= 80 and w["score"] < 40


def test_points_sum_to_score():
    m = score_candidate(parse_jd(JD_TEXT), _resume(STRONG))
    assert abs(sum(b["points"] for b in m["breakdown"]) - m["score"]) < 0.5
    assert abs(sum(b["weight"] for b in m["breakdown"]) - 1) < 1e-6


def test_missing_component_weights_are_renormalised():
    jd = parse_jd("Engineer\nRequirements\nJava and SQL experience required.")
    assert jd["min_years"] is None and jd["education"]["min_level"] == 0
    m = score_candidate(jd, _resume(STRONG))
    applied = {b["key"] for b in m["breakdown"] if b["applied"]}
    assert "experience" not in applied and "education" not in applied


def test_substitute_skill_gets_partial_credit():
    jd = parse_jd(JD_TEXT)
    r = _resume(STRONG.replace("PostgreSQL", "MySQL"))
    m = score_candidate(jd, r)
    partial = {p["skill"]: p for p in m["skills"]["partial"]}
    assert partial["PostgreSQL"]["via"] == ["MySQL"] and partial["PostgreSQL"]["credit"] == 0.5


def test_semantic_evidence_for_unnamed_skill():
    jd = parse_jd(JD_TEXT)
    text = STRONG.replace("Kafka event streams", "a real-time event streaming platform publishing and consuming "
                                                 "messages between services").replace(", Kafka", "")
    m = score_candidate(jd, _resume(text))
    kafka = next(p for p in m["skills"]["partial"] if p["skill"] == "Kafka")
    assert kafka["how"] == "semantically implied"


def test_unrelated_experience_counts_a_quarter_capped_at_half_the_requirement():
    jd = parse_jd(JD_TEXT)
    r = _resume(STRONG)
    r2 = copy.deepcopy(r)
    r2["experience"][0]["title"] = "Pastry Chef"
    r2["experience"][0]["description"] = "Baked bread and cakes for a busy bakery."
    e1 = score_candidate(jd, r)["experience"]
    e2 = score_candidate(jd, r2)["experience"]
    assert e1["relevant_years"] > 0 and e2["relevant_years"] == 0
    expected = min(0.25 * e2["candidate_years"], 0.5 * e2["required_min"])
    assert abs(e2["effective_years"] - expected) < 0.11
    # however much unrelated experience someone has, it never meets the requirement on its own
    r3 = copy.deepcopy(r2)
    r3["total_years"] = 40.0
    e3 = score_candidate(jd, r3)["experience"]
    assert e3["effective_years"] <= 0.5 * e3["required_min"] and e3["score"] <= 0.5


def test_reasons_are_generated(samples):
    jd = parse_jd((samples / "job_descriptions" / "senior_java_backend_engineer.txt").read_text())
    f = samples / "resumes" / "hannah_weber.pdf"
    m = score_candidate(jd, parse_resume(extract_text(f.name, f.read_bytes()), f.name))
    text = " ".join(r["text"] for r in m["reasons"])
    assert "Missing required skills" in text and "unrelated" in text


def test_sample_ranking_is_sensible(samples):
    jd = parse_jd((samples / "job_descriptions" / "senior_java_backend_engineer.txt").read_text())
    scores = {}
    for f in (samples / "resumes").iterdir():
        p = parse_resume(extract_text(f.name, f.read_bytes()), f.name)
        scores[p["name"]] = score_candidate(jd, p)["score"]
    ranked = sorted(scores, key=scores.get, reverse=True)
    assert set(ranked[:3]) == {"Aarav Mehta", "Rohan Iyer", "Lucia Fernandes"}
    assert set(ranked[-3:]) <= {"Tom Becker", "Karan Desai", "Priya Venkatesh", "Nisha Kapoor"}
