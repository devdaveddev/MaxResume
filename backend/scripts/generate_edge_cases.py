"""Generate hard, real-world-style resume files to exercise the ingestion pipeline.

Output: sample_data/edge_cases/
  two_column.pdf        sidebar layout (contact/skills/education left, experience right)
  scanned.pdf           image-only PDF (no text layer) -> needs OCR
  encrypted.pdf         password-protected PDF -> must be rejected cleanly
  header_contact.docx   name/contact in the page header, "LinkedIn" hyperlink label
  legacy.doc / resume.rtf / resume.odt   converted with LibreOffice (skipped if not installed)
  tricky_dates.txt      unusual date formats, overlapping roles, a career gap
  renamed_image.pdf     a PNG renamed to .pdf -> must be rejected
  truncated.pdf         a damaged PDF -> must be rejected

All people and contact details are fictional.
Run: uv run python scripts/generate_edge_cases.py
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from pathlib import Path

from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parents[2] / "sample_data" / "edge_cases"
FONT_CANDIDATES = ["/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                   "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf"]

SCANNED_LINES = [
    "RAVI SHANKAR",
    "ravi.shankar@example.com | +91 98450 55507 | Pune, India",
    "",
    "EXPERIENCE",
    "Senior Java Developer | Tidal Systems | Mar 2020 - Present",
    "Built Spring Boot microservices and Kafka consumers on AWS.",
    "Java Developer | Nimbus Soft | Jun 2017 - Feb 2020",
    "Developed REST APIs with Spring and PostgreSQL.",
    "",
    "SKILLS",
    "Java, Spring Boot, Kafka, PostgreSQL, Docker, Kubernetes, AWS",
    "",
    "EDUCATION",
    "B.Tech in Computer Science, Pune University, 2017",
]

TRICKY_DATES = """Elena Petrova
elena.petrova@example.com  ·  (555) 014-2233  ·  Denver, CO

Summary
Platform engineer with 8+ years of experience.

Experience
Staff Engineer, Quartz Labs                      Since March 2022
Lead the platform team; Kubernetes, Terraform and Go services.

Senior Engineer — Bluebird Analytics             Jan '19 – Feb '22
Built data pipelines in Python and Spark on AWS.

Freelance Consultant                             2019 to 2020
Part-time consulting alongside the Bluebird role (overlaps, must not be double counted).

Software Engineer at Copperline                  06/2015 to 08/2017
Java services and PostgreSQL.

Education
M.S. Computer Science, University of Colorado, 2015, GPA 3.8/4.0
"""


def _font(size: int):
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def two_column_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, h - 50, "Amara Okonkwo")
    c.setFont("Helvetica", 10)
    c.drawString(40, h - 66, "Senior Backend Engineer")
    left = ["CONTACT", "amara.okonkwo@example.com", "+44 555 0182 331", "Leeds, UK", "",
            "SKILLS", "Java", "Spring Boot", "Kafka", "PostgreSQL", "Docker", "Kubernetes", "AWS", "",
            "EDUCATION", "BSc Computer Science", "University of Leeds", "2016"]
    right = ["EXPERIENCE", "Senior Backend Engineer | Ledgerline | Feb 2021 - Present",
             "Designed Spring Boot microservices for a payments ledger.",
             "Introduced Kafka event streaming between services.",
             "Ran workloads on Kubernetes in AWS with Docker images.",
             "", "Backend Engineer | Quayside Tech | Sep 2016 - Jan 2021",
             "Built REST APIs in Java with PostgreSQL storage.",
             "Wrote JUnit tests and maintained CI pipelines in Jenkins.",
             "", "PROJECTS", "Open-source contributor to a Java rate-limiter library."]
    for i, line in enumerate(left):
        c.setFont("Helvetica-Bold" if line.isupper() else "Helvetica", 9.5)
        c.drawString(40, h - 110 - i * 15, line)
    for i, line in enumerate(right):
        c.setFont("Helvetica-Bold" if line.isupper() else "Helvetica", 9.5)
        c.drawString(215, h - 110 - i * 15, line)
    c.linkURL("https://www.linkedin.com/in/amara-okonkwo-demo", (40, h - 400, 200, h - 385))
    c.drawString(40, h - 395, "LinkedIn")
    c.save()


def scanned_pdf(path: Path) -> None:
    img = Image.new("L", (1654, 2339), 255)  # A4 at 200 dpi
    d = ImageDraw.Draw(img)
    y = 120
    for line in SCANNED_LINES:
        size = 46 if line == SCANNED_LINES[0] else 30
        d.text((120, y), line, fill=0, font=_font(size))
        y += size + 22
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawImage(ImageReader(io.BytesIO(buf.getvalue())), 0, 0, width=A4[0], height=A4[1])
    c.save()


def encrypted_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4, encrypt="s3cret-pass")
    c.drawString(72, 750, "Confidential resume")
    c.save()


def _add_hyperlink(paragraph, url: str, text: str) -> None:
    r_id = paragraph.part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = text
    run.append(t)
    link.append(run)
    paragraph._p.append(link)


def header_docx(path: Path) -> None:
    doc = Document()
    header = doc.sections[0].header
    header.paragraphs[0].text = "Jonas Lindqvist"
    header.add_paragraph("jonas.lindqvist@example.com | +46 555 123 456 | Stockholm, Sweden")
    p = header.add_paragraph()
    _add_hyperlink(p, "https://www.linkedin.com/in/jonas-lindqvist-demo", "LinkedIn")
    p.add_run(" | ")
    _add_hyperlink(p, "https://github.com/jonas-lindqvist-demo", "GitHub")
    doc.add_heading("Experience", level=2)
    doc.add_paragraph("Backend Developer | Nordbyte AB | Apr 2019 – Present").runs[0].bold = True
    doc.add_paragraph("Build Java and Spring Boot services; PostgreSQL and Docker.", style="List Bullet")
    doc.add_heading("Skills", level=2)
    doc.add_paragraph("Java, Spring Boot, PostgreSQL, Docker, Git")
    doc.add_heading("Education", level=2)
    doc.add_paragraph("M.Sc. in Software Engineering, KTH Royal Institute of Technology, 2019")
    doc.save(str(path))


def libreoffice_convert(src: Path, fmt: str, dest: Path) -> bool:
    office = shutil.which("soffice") or shutil.which("libreoffice")
    if not office:
        return False
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([office, f"-env:UserInstallation=file://{tmp}/profile", "--headless", "--convert-to", fmt,
                        "--outdir", tmp, str(src)], capture_output=True, timeout=120, check=False)
        produced = next(Path(tmp).glob(f"{src.stem}.*{dest.suffix}"), None) or next(
            (p for p in Path(tmp).iterdir() if p.suffix == dest.suffix), None)
        if not produced:
            return False
        shutil.copy(produced, dest)
    return True


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    two_column_pdf(OUT / "two_column.pdf")
    scanned_pdf(OUT / "scanned.pdf")
    encrypted_pdf(OUT / "encrypted.pdf")
    header_docx(OUT / "header_contact.docx")
    (OUT / "tricky_dates.txt").write_text(TRICKY_DATES)
    png = io.BytesIO()
    Image.new("RGB", (10, 10)).save(png, format="PNG")
    (OUT / "renamed_image.pdf").write_bytes(png.getvalue())
    (OUT / "truncated.pdf").write_bytes((OUT / "two_column.pdf").read_bytes()[:400])
    converted = [libreoffice_convert(OUT / "header_contact.docx", fmt, OUT / name)
                 for fmt, name in (("doc:MS Word 97", "legacy.doc"), ("rtf", "resume.rtf"), ("odt", "resume.odt"))]
    print(f"Wrote edge cases to {OUT} (LibreOffice conversions: {sum(converted)}/3)")


if __name__ == "__main__":
    main()
