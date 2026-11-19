from datetime import date

from app.nlp.dates import merge_intervals, parse_date, total_months
from app.nlp.jd_parser import parse_jd
from app.nlp.resume_parser import parse_resume
from app.nlp.sections import split_sections
from app.nlp.skills import extract_alternatives, extract_skills
from app.nlp.text_extract import extract_text

TODAY = date(2026, 11, 1)


def test_alias_matching_and_boundaries():
    s = extract_skills("Built services in Java 17 with Spring Boot, Postgres and k8s; some JavaScript.")
    assert {"Java", "Spring Boot", "PostgreSQL", "Kubernetes", "JavaScript"} <= s.keys()
    assert "Spring Framework" not in s


def test_ambiguous_words_are_not_skills():
    s = extract_skills("I excel at the rest of the work. Graduated Spring 2021. Let's go.")
    assert not {"Excel", "REST APIs", "Spring Framework", "Go"} & s.keys()


def test_symbols_in_skill_names():
    s = extract_skills("C++, C#, .NET Core, Node.js and CI/CD pipelines")
    assert {"C++", "C#", ".NET", "Node.js", "CI/CD"} <= s.keys()


def test_alternatives_and_or_similar():
    groups, similar = extract_alternatives("CI with Jenkins or GitHub Actions\nKafka or similar message brokers")
    assert ["Jenkins", "GitHub Actions"] in groups
    assert "Kafka" in similar


def test_date_parsing_variants():
    assert parse_date("Mar 2019") == date(2019, 3, 1)
    assert parse_date("Sept 2020") == date(2020, 9, 1)
    assert parse_date("03/2019") == date(2019, 3, 1)
    assert parse_date("2019", is_end=True) == date(2019, 12, 1)
    assert parse_date("Present", today=TODAY) == TODAY


def test_overlapping_jobs_not_double_counted():
    a = (date(2020, 1, 1), date(2021, 12, 1))
    b = (date(2021, 1, 1), date(2022, 12, 1))
    assert len(merge_intervals([a, b])) == 1
    assert total_months([a, b]) == 36


def test_section_split_with_inline_heading():
    s = split_sections("Jane Doe\nSkills: Java, SQL\nWORK EXPERIENCE\nDev at X\nEducation\nB.Tech")
    assert s["skills"] == "Java, SQL" and "Dev at X" in s["experience"] and "B.Tech" in s["education"]


def test_pdf_resume_layout_a(samples):
    f = samples / "resumes" / "aarav_mehta.pdf"
    r = parse_resume(extract_text(f.name, f.read_bytes()), f.name, today=TODAY)
    assert r["name"] == "Aarav Mehta"
    assert r["email"] == "aarav.mehta@example.com"
    assert r["phone"].replace(" ", "") == "+919876555501"
    assert [x["company"] for x in r["experience"]] == ["Finlytics Payments", "Kestrel Commerce"]
    assert r["experience"][0]["title"] == "Senior Software Engineer"
    assert 7.0 <= r["total_years"] <= 7.6
    assert r["highest_degree"] == "Bachelor's" and r["education"][0]["field"] == "Computer Science"


def test_docx_resume_with_skills_table_layout_c(samples):
    f = samples / "resumes" / "rohan_iyer.docx"
    r = parse_resume(extract_text(f.name, f.read_bytes()), f.name, today=TODAY)
    assert r["name"] == "Rohan Iyer"
    assert len(r["experience"]) == 3
    assert r["experience"][0]["company"] == "Orbit Pay"
    skills = {s["name"]: s for s in r["skills"]}
    assert skills["Terraform"]["listed"]
    assert r["highest_degree"] == "Master's"


def test_company_first_layout_b(samples):
    f = samples / "resumes" / "emily_novak.pdf"
    r = parse_resume(extract_text(f.name, f.read_bytes()), f.name, today=TODAY)
    assert r["experience"][0]["title"] == "Senior Backend Engineer"
    assert r["experience"][0]["company"].startswith("Cloudberry Health")


def test_degree_name_is_not_a_soft_skill(samples):
    f = samples / "resumes" / "arjun_nair.docx"
    r = parse_resume(extract_text(f.name, f.read_bytes()), f.name, today=TODAY)
    assert "Communication" not in r["soft_skills"]


def test_jd_parsing(samples):
    jd = parse_jd((samples / "job_descriptions" / "senior_java_backend_engineer.txt").read_text())
    assert jd["title"] == "Senior Java Backend Engineer"
    assert {"Java", "Spring Boot", "Kafka", "PostgreSQL", "Kubernetes"} <= set(jd["required_skills"])
    assert {"Redis", "Terraform", "GraphQL"} <= set(jd["preferred_skills"])
    assert not set(jd["required_skills"]) & set(jd["preferred_skills"])
    assert jd["min_years"] == 5
    assert jd["education"]["min_level"] == 2 and jd["education"]["equivalent_experience_ok"]
    assert ["Jenkins", "GitHub Actions"] in jd["alternatives"]
    assert not any("salary" in r.lower() for r in jd["requirements"])


def test_jd_without_headings_uses_line_cues():
    jd = parse_jd("Python Developer\nWe need 3-5 years of experience with Python and Django.\n"
                  "Knowledge of AWS is a plus.\nMaster's degree preferred.")
    assert "Python" in jd["required_skills"] and "AWS" in jd["preferred_skills"]
    assert (jd["min_years"], jd["max_years"]) == (3, 5)


def test_pasted_jd_with_crlf_and_bullets():
    from app.service import build_job

    job = build_job("Backend Engineer\r\nLocation: Pune\r\n\r\nRequirements\r\n• 3+ years of Java experience\r\n"
                    "• Build REST APIs with Spring Boot\r\n", None)
    assert job["title"] == "Backend Engineer"
    assert job["parsed"]["requirements"] == ["Build REST APIs with Spring Boot"]
    assert job["parsed"]["min_years"] == 3
