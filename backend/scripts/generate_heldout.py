"""Resumes in layouts the parser was NOT developed against, with ground truth.

Two groups, kept separate on purpose:

  dev       4 resumes written to probe weaknesses. Their first run exposed 6 parser bugs,
            which were then fixed, so they are no longer an unbiased test.
  heldout   3 resumes written afterwards, with ground truth fixed *before* the first run.
            First (blind) run: 92.2% field accuracy (47/51), skills F1 100%. The only failure,
            "Senior Consultant @ Deloitte" ('@' not understood as 'at'), was fixed afterwards,
            so later runs of this group are no longer blind. 92.2% is the honest figure.

Layout styles covered: Indian-format CV with experience/education tables, "NAME — Title"
headers with bracketed dates, non-standard headings, plain text "2018 - 2021: Role at Co",
date-first table rows, "Title — Company — City" with dates on the next line, "Role @ Company".

All people, companies and contact details are fictional.
Run: uv run python scripts/generate_heldout.py
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate

OUT = Path(__file__).resolve().parents[2] / "sample_data" / "heldout"

TRUTH = {
    "ananya_iyer.docx": dict(group="dev", name="Ananya Iyer", email="ananya.iyer@example.com", phone="919845012345",
        location="Chennai, Tamil Nadu", roles=[("Software Engineer", "Zoho Corporation", "2021-07", None),
        ("Associate Software Engineer", "Freshworks", "2019-06", "2021-06")],
        education=[(2, "Anna University", 2019)],
        skills={"Python", "Django", "Flask", "PostgreSQL", "Docker", "Git", "Linux"}),
    "priya_nair.pdf": dict(group="dev", name="Priya Nair", email="priya.nair@example.com", phone="14155550142",
        location="San Francisco, CA", roles=[("Data Engineer", "Acme Analytics", "2021-03", None),
        ("Analytics Engineer", "Brightline Retail", "2018-08", "2021-02")],
        education=[(3, "University of San Francisco", 2018)],
        skills={"Python", "SQL", "Airflow", "dbt", "Snowflake", "Spark", "Tableau", "AWS"}),
    "marco_bianchi.docx": dict(group="dev", name="Marco Bianchi", email="marco.bianchi@example.com", phone="395551234567",
        location="Milan, Italy", roles=[("Senior Backend Developer", "Northwind Logistics", "2020-01", None),
        ("Backend Developer", "Contoso Bank", "2017-01", "2019-12")],
        education=[(3, "Politecnico di Milano", 2016)],
        skills={"Java", "Go", "Spring Boot", "Kafka", "Kubernetes", "Oracle DB", "Docker"}),
    "sam_okoro.txt": dict(group="dev", name="Sam Okoro", email="sam.okoro@example.com", phone="7700900123",
        location="Manchester, UK", roles=[("QA Engineer", "Pinewood Games", "2021-01", None),
        ("Junior Developer", "XYZ Ltd", "2018-01", "2021-12")],
        education=[(2, "University of Salford", 2018)],
        skills={"Selenium", "Python", "PHP", "MySQL", "Jira", "Git"}),
    "lena_fischer.docx": dict(group="heldout", name="Lena Fischer", email="lena.fischer@example.com", phone="4930555012345",
        location="Berlin, Germany", roles=[("Lead Developer", "Initech", "2020-03", None),
        ("Software Developer", "Globex", "2016-09", "2020-02")],
        education=[(3, "Technische Universität München", 2016)],
        skills={"TypeScript", "Node.js", "React", "PostgreSQL", "AWS", "Docker"}),
    "arjun_mehra.pdf": dict(group="heldout", name="Arjun Mehra", email="arjun.mehra@example.com", phone="919811055501",
        location="Gurugram, India", roles=[("Software Engineer II", "Stripe", "2019-09", "2023-05"),
        ("Senior Software Engineer", "Razorpay", "2023-06", None)],
        education=[(2, "VIT University", 2019)],
        skills={"Java", "Kotlin", "Spring Boot", "Kafka", "MySQL", "Redis", "AWS"}),
    "nadia_rahman.txt": dict(group="heldout", name="Nadia Rahman", email="nadia.rahman@example.com", phone="15125550199",
        location="Austin, TX", roles=[("Senior Consultant", "Deloitte", "2020-01", "2024-12"),
        ("Business Analyst", "Accenture", "2017-01", "2019-12")],
        education=[(3, "University of Texas at Austin", 2017)],
        skills={"SQL", "Excel", "Power BI", "Python", "Tableau", "Agile"}),
}


def _ananya(path: Path) -> None:
    d = Document()
    d.add_paragraph("CURRICULUM VITAE")
    for line in ["Name: Ananya Iyer", "Mobile: +91-98450-12345", "E-mail: ananya.iyer@example.com",
                 "Address: Chennai, Tamil Nadu"]:
        d.add_paragraph(line)
    d.add_paragraph("CAREER OBJECTIVE")
    d.add_paragraph("Seeking a challenging role as a Python developer where I can apply my skills in Django, "
                    "REST APIs and PostgreSQL.")
    d.add_paragraph("WORK EXPERIENCE")
    t = d.add_table(rows=1, cols=3)
    for i, h in enumerate(["Company", "Designation", "Duration"]):
        t.rows[0].cells[i].text = h
    for row in [("Zoho Corporation", "Software Engineer", "July 2021 – Present"),
                ("Freshworks", "Associate Software Engineer", "June 2019 – June 2021")]:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = v
    d.add_paragraph("Responsibilities: Developed Django REST APIs, wrote PostgreSQL queries, containerised services with Docker.")
    d.add_paragraph("TECHNICAL SKILLS")
    d.add_paragraph("Python, Django, Flask, PostgreSQL, Docker, Git, Linux")
    d.add_paragraph("EDUCATIONAL QUALIFICATION")
    t = d.add_table(rows=1, cols=4)
    for i, h in enumerate(["Degree", "Institute", "Year", "Percentage"]):
        t.rows[0].cells[i].text = h
    cells = t.add_row().cells
    for i, v in enumerate(["B.E. Computer Science", "Anna University", "2019", "82%"]):
        cells[i].text = v
    d.add_paragraph("DECLARATION")
    d.add_paragraph("I hereby declare that the above information is true to the best of my knowledge.")
    d.save(str(path))


def _pdf(path: Path, blocks: list[tuple[str, str]]) -> None:
    ss = getSampleStyleSheet()
    SimpleDocTemplate(str(path), pagesize=A4).build([Paragraph(text, ss[style]) for style, text in blocks])


def _docx(path: Path, blocks: list[tuple[str | None, str]]) -> None:
    d = Document()
    for style, text in blocks:
        if style:
            d.add_heading(text, level=int(style[-1]))
        else:
            d.add_paragraph(text)
    d.save(str(path))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _ananya(OUT / "ananya_iyer.docx")
    _pdf(OUT / "priya_nair.pdf", [
        ("Title", "PRIYA NAIR — Data Engineer"),
        ("Normal", "priya.nair@example.com · +1 (415) 555-0142 · San Francisco, CA · github.com/priyanair-demo"),
        ("Heading3", "Experience"), ("Normal", "<b>Data Engineer, Acme Analytics (Mar 2021 – Present)</b>"),
        ("Normal", "• Built Airflow pipelines loading 2TB/day into Snowflake; modelled data with dbt."),
        ("Normal", "<b>Analytics Engineer, Brightline Retail (Aug 2018 – Feb 2021)</b>"),
        ("Normal", "• Wrote SQL and Python ETL jobs; built Tableau dashboards for merchandising."),
        ("Heading3", "Skills"), ("Normal", "Python · SQL · Airflow · dbt · Snowflake · Spark · Tableau · AWS"),
        ("Heading3", "Education"), ("Normal", "MS, Data Science — University of San Francisco, 2018")])
    _docx(OUT / "marco_bianchi.docx", [
        ("H1", "Marco Bianchi"), (None, "Milan, Italy | marco.bianchi@example.com | +39 555 123 4567"),
        ("H2", "Professional Background"),
        (None, "Northwind Logistics — Senior Backend Developer"), (None, "Jan. 2020 – Present"),
        (None, "Designing Go and Java microservices on Kubernetes; Kafka event pipelines."),
        (None, "Contoso Bank — Backend Developer"), (None, "Jan. 2017 – Dec. 2019"),
        (None, "Java and Spring Boot services backed by Oracle."),
        ("H2", "Core Skills"), (None, "Java • Go • Spring Boot • Kafka • Kubernetes • Oracle DB • Docker"),
        ("H2", "Academic Qualifications"),
        (None, "Laurea Magistrale (Master's) in Computer Engineering, Politecnico di Milano, 2016")])
    (OUT / "sam_okoro.txt").write_text(
        "Sam Okoro\nsam.okoro@example.com\n07700 900123\nManchester, UK\n\nEXPERIENCE\n"
        "2021 - present: QA Engineer at Pinewood Games\nAutomated test suites with Selenium and Python.\n"
        "2018 - 2021: Junior Developer at XYZ Ltd\nMaintained PHP and MySQL web applications.\n\n"
        "SKILLS\nSelenium, Python, PHP, MySQL, Jira, Git\n\n"
        "EDUCATION\nBSc Computer Science, University of Salford (2018)\n")

    _docx(OUT / "lena_fischer.docx", [
        ("H1", "Lena Fischer"), (None, "lena.fischer@example.com · +49 30 555012345 · Berlin, Germany"),
        ("H2", "Work History"),
        (None, "03/2020 – current | Lead Developer | Initech"),
        (None, "Leads a team of five building TypeScript and Node.js services; React front end; deploys to AWS with Docker."),
        (None, "09/2016 – 02/2020 | Software Developer | Globex"),
        (None, "Built REST services in Node.js backed by PostgreSQL."),
        ("H2", "Technologies"), (None, "TypeScript, Node.js, React, PostgreSQL, AWS, Docker"),
        ("H2", "Education"), (None, "M.Sc. Informatics, Technische Universität München, 2016")])
    _pdf(OUT / "arjun_mehra.pdf", [
        ("Title", "Arjun Mehra"),
        ("Normal", "Gurugram, India | +91 98110 55501 | arjun.mehra@example.com"),
        ("Heading3", "Professional Experience"),
        ("Normal", "<b>Senior Software Engineer — Razorpay — Bengaluru</b>"), ("Normal", "June 2023 to Present"),
        ("Normal", "• Own the payouts service in Kotlin and Spring Boot; Kafka for settlement events; Redis caching."),
        ("Normal", "<b>Software Engineer II — Stripe — Dublin</b>"), ("Normal", "September 2019 to May 2023"),
        ("Normal", "• Built Java services on AWS with MySQL; on-call for the billing platform."),
        ("Heading3", "Skills"),
        ("Normal", "Languages: Java, Kotlin"), ("Normal", "Frameworks: Spring Boot"),
        ("Normal", "Data &amp; infra: Kafka, MySQL, Redis, AWS"),
        ("Heading3", "Education"),
        ("Normal", "Bachelor of Technology (Information Technology) | VIT University | 2019")])
    (OUT / "nadia_rahman.txt").write_text(
        "NADIA RAHMAN\nAustin, TX • (512) 555-0199 • nadia.rahman@example.com\n\n"
        "SUMMARY\nAnalytics consultant with over 7 years of experience turning data into decisions.\n\n"
        "EMPLOYMENT\nSenior Consultant @ Deloitte, 2020 – 2024\n"
        "Delivered Power BI and Tableau dashboards; wrote SQL and Python for client analytics in Agile teams.\n"
        "Business Analyst @ Accenture, 2017 – 2019\nRequirements analysis, Excel models and SQL reporting.\n\n"
        "SKILLS\nSQL, Excel, Power BI, Python, Tableau, Agile\n\n"
        "EDUCATION\nMBA (Business Analytics), University of Texas at Austin, 2017\n")
    print(f"Wrote {len(TRUTH)} resumes to {OUT}")


if __name__ == "__main__":
    main()
