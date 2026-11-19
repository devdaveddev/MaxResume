"""Demo set for the walkthrough video: one job description and five resumes.

Each resume is built to show one capability on camera:

  1. ishaan_verma.pdf     strong fit: required skills used in real work, enough years
  2. clara_mendes.docx    same skills in other words: "event streaming platform" credited as Kafka by
                          meaning; Django, MySQL and GCP as substitutes for FastAPI, PostgreSQL and AWS
  3. tomas_reyes.pdf      career switcher: 8 years total, only 2 in software (unrelated years capped)
  4. aisha_khan.pdf       two-column sidebar layout, read column by column
  5. oliver_grant.docx    wrong field (product designer): clear weak match

All people, companies and contact details are fictional (example.com, 555 numbers).
Run: uv run python scripts/generate_video_demo.py
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from generate_samples import write_docx, write_pdf

OUT = Path(__file__).resolve().parents[2] / "sample_data" / "video_demo"

JD_TITLE = "Python Backend Engineer"
JD_SECTIONS = [
    ("About Us", ["Ledgerly builds invoicing and payments software for small businesses in 12 countries."]),
    ("Key Responsibilities", [
        "Design and build REST APIs in Python with FastAPI for our billing platform.",
        "Model data and write efficient SQL queries in PostgreSQL.",
        "Build event-driven services with Kafka or similar message brokers.",
        "Containerise services with Docker and deploy them to AWS.",
        "Use Redis for caching and rate limiting.",
        "Write automated tests with pytest and maintain CI/CD pipelines.",
    ]),
    ("Requirements", [
        "4+ years of professional experience in backend development.",
        "Strong Python skills and experience with FastAPI.",
        "Solid knowledge of PostgreSQL and SQL.",
        "Experience with Kafka or similar message brokers.",
        "Hands-on experience with Docker and AWS.",
        "Experience with Redis.",
        "Comfortable with Git and CI/CD pipelines.",
        "Bachelor's degree in Computer Science or a related field.",
    ]),
    ("Nice to Have", [
        "Experience with Kubernetes.",
        "Familiarity with Terraform.",
        "Knowledge of GraphQL.",
        "Exposure to Prometheus and Grafana.",
    ]),
    ("What We Offer", ["Remote-first team, learning budget and health insurance."]),
]

CANDIDATES = [
    dict(file="ishaan_verma.pdf", layout="A", name="Ishaan Verma", email="ishaan.verma@example.com",
         phone="+91 98450 55511", location="Bengaluru, India", linkedin="linkedin.com/in/ishaan-verma-demo",
         summary="Backend engineer with 6 years of experience building Python APIs for fintech.",
         skills="Python, FastAPI, PostgreSQL, SQL, Kafka, Redis, Docker, AWS, Kubernetes, pytest, GitHub Actions, Git, Terraform",
         roles=[("Senior Backend Engineer", "Paystack Labs", "Bengaluru", "Mar 2022", "Present", [
             "Built FastAPI services for invoicing used by 40,000 merchants, deployed with Docker on AWS (EKS).",
             "Designed Kafka event pipelines for payment settlement processing 2M events a day.",
             "Tuned PostgreSQL queries and added Redis caching, cutting p95 latency from 320ms to 70ms.",
             "Wrote pytest suites and GitHub Actions CI/CD pipelines; provisioned infrastructure with Terraform."]),
             ("Backend Engineer", "Kredit Systems", "Pune", "Jul 2020", "Feb 2022", [
             "Developed REST APIs in Python with FastAPI and PostgreSQL for loan origination.",
             "Containerised services with Docker and maintained CI pipelines."])],
         education=[("B.Tech in Computer Science", "National Institute of Technology, Surathkal", "2020")],
         certs=["AWS Certified Developer – Associate"]),

    dict(file="clara_mendes.docx", layout="B", name="Clara Mendes", email="clara.mendes@example.com",
         phone="+351 555 210 444", location="Lisbon, Portugal", linkedin="linkedin.com/in/clara-mendes-demo",
         summary="Python developer with 5 years of experience building web backends.",
         skills="Python, Django, MySQL, Docker, GCP, Redis, pytest, Git, GitLab CI",
         roles=[("Software Engineer", "Mercado Digital", "Lisbon", "Jan 2022", "Present", [
             "Build Django REST services for order management, deployed on Google Cloud.",
             "Built a real-time event streaming platform that publishes and consumes order events between independently deployable services.",
             "Model data in MySQL and use Redis for caching; write pytest suites run in GitLab CI."]),
             ("Junior Developer", "Atlantico Web", "Porto", "Sep 2020", "Dec 2021", [
             "Maintained Python REST APIs in Django, wrote SQL reports and Docker-based test environments."])],
         education=[("M.Sc. in Software Engineering", "University of Porto", "2020")],
         certs=[]),

    dict(file="tomas_reyes.pdf", layout="C", name="Tomas Reyes", email="tomas.reyes@example.com",
         phone="+1 555 014 3321", location="Denver, CO", linkedin=None,
         summary="Mechanical engineer turned backend developer, building Python services since 2024.",
         skills="Python, FastAPI, PostgreSQL, SQL, Docker, Git, AutoCAD, Excel",
         roles=[("Backend Developer", "Trailhead Software", "Denver", "Nov 2024", "Present", [
             "Build FastAPI endpoints and PostgreSQL queries for a booking platform.",
             "Containerised two services with Docker."]),
             ("Mechanical Design Engineer", "Rocky Mountain Pumps", "Denver", "Jan 2019", "Oct 2024", [
             "Designed industrial pump assemblies in AutoCAD and ran tolerance analysis.",
             "Managed supplier quality reviews and production cost models in Excel."])],
         education=[("B.S. in Mechanical Engineering", "Colorado State University", "2018")],
         certs=["Python for Everybody (Coursera)"]),

    dict(file="oliver_grant.docx", layout="A", name="Oliver Grant", email="oliver.grant@example.com",
         phone="+44 555 0177 210", location="Bristol, UK", linkedin="linkedin.com/in/oliver-grant-demo",
         summary="Product designer with 6 years of experience in SaaS onboarding and design systems.",
         skills="Figma, User Research, Prototyping, Design Systems, HTML, CSS, Accessibility",
         roles=[("Senior Product Designer", "Brightdesk", "Bristol", "Apr 2022", "Present", [
             "Lead onboarding design for a SaaS help-desk product; run user research and usability tests.",
             "Maintain the Figma design system used by 4 product teams."]),
             ("Product Designer", "Pixel & Co", "Bath", "Jun 2020", "Mar 2022", [
             "Designed web and mobile flows; built HTML and CSS prototypes with accessibility reviews."])],
         education=[("BA in Graphic Design", "University of the West of England", "2020")],
         certs=[]),
]


def write_jd_docx(path: Path) -> None:
    doc = Document()
    doc.add_heading(JD_TITLE, level=1)
    doc.add_paragraph("Location: Remote (Europe / India time zones)")
    for heading, lines in JD_SECTIONS:
        doc.add_heading(heading, level=2)
        for line in lines:
            doc.add_paragraph(line, style=None if heading in ("About Us", "What We Offer") else "List Bullet")
    doc.save(str(path))


def write_two_column_pdf(path: Path) -> None:
    """Aisha Khan: sidebar layout (contact, skills, education left; experience right)."""
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, h - 50, "Aisha Khan")
    c.setFont("Helvetica", 10)
    c.drawString(40, h - 66, "Python Backend Developer")
    left = ["CONTACT", "aisha.khan@example.com", "+971 55 555 0142", "Dubai, UAE", "",
            "SKILLS", "Python", "Flask", "PostgreSQL", "SQL", "Docker", "Kubernetes", "AWS", "Redis", "Git", "",
            "EDUCATION", "BSc Computer Science", "University of Sharjah", "2020"]
    right = ["EXPERIENCE", "Backend Developer | Desert Logistics | Jan 2022 - Present",
             "Build Flask REST APIs for shipment tracking backed by PostgreSQL.",
             "Run services on Kubernetes in AWS with Docker; Redis for caching.",
             "Wrote unit tests and maintained CI/CD pipelines.",
             "", "Junior Developer | Oasis Apps | Aug 2020 - Dec 2021",
             "Built internal Python tools and SQL reports.",
             "", "PROJECTS", "Open-source contributor to a Python rate-limiting library."]
    for i, line in enumerate(left):
        c.setFont("Helvetica-Bold" if line.isupper() else "Helvetica", 9.5)
        c.drawString(40, h - 110 - i * 15, line)
    for i, line in enumerate(right):
        c.setFont("Helvetica-Bold" if line.isupper() else "Helvetica", 9.5)
        c.drawString(215, h - 110 - i * 15, line)
    c.save()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_jd_docx(OUT / "job_description_python_backend.docx")
    for cand in CANDIDATES:
        path = OUT / cand["file"]
        (write_pdf if path.suffix == ".pdf" else write_docx)(cand, path)
    write_two_column_pdf(OUT / "aisha_khan.pdf")
    print(f"Wrote 1 job description and {len(CANDIDATES) + 1} resumes to {OUT}")


if __name__ == "__main__":
    main()
