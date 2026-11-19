"""Ingestion: type sniffing, safety limits, and hard real-world layouts."""

import io
import shutil
import zipfile
from datetime import date

import pytest

from app.ingest.detect import FileRejected, sniff
from app.ingest.extractors import extract, normalize_text
from app.nlp.quality import assess
from app.nlp.resume_parser import parse_resume

TODAY = date(2026, 11, 1)
needs_office = pytest.mark.skipif(not (shutil.which("soffice") or shutil.which("libreoffice")),
                                  reason="LibreOffice not installed")
needs_ocr = pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract not installed")


def _parse(samples, name):
    f = samples / "edge_cases" / name
    ex = extract(f.name, f.read_bytes())
    profile = parse_resume(ex.text, f.name, today=TODAY, links=ex.links)
    return ex, profile, assess(profile, ex.meta())


def test_type_is_sniffed_from_content_not_extension(samples):
    data = (samples / "resumes" / "aarav_mehta.pdf").read_bytes()
    kind, warnings = sniff(data, "resume.docx")
    assert kind == "pdf" and "does not match" in warnings[0]


@pytest.mark.parametrize("name,code", [("renamed_image.pdf", "unsupported"), ("truncated.pdf", "corrupt"),
                                       ("encrypted.pdf", "encrypted")])
def test_bad_files_are_rejected_with_a_reason(samples, name, code):
    with pytest.raises(FileRejected) as e:
        extract(name, (samples / "edge_cases" / name).read_bytes())
    assert e.value.code == code


def test_executables_and_empty_files_rejected():
    with pytest.raises(FileRejected) as e:
        sniff(b"MZ\x90\x00" + b"\x00" * 100, "cv.pdf")
    assert e.value.code == "unsupported"
    with pytest.raises(FileRejected) as e:
        sniff(b"", "cv.pdf")
    assert e.value.code == "empty"


def test_zip_bomb_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", b"0" * (70 * 1024 * 1024))
    with pytest.raises(FileRejected) as e:
        sniff(buf.getvalue(), "cv.docx")
    assert e.value.code == "zip_bomb"


def test_oversized_file_rejected(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_file_mb", 0.001)
    with pytest.raises(FileRejected) as e:
        sniff(b"%PDF-1.4" + b"x" * 5000, "cv.pdf")
    assert e.value.code == "too_large"


def test_normalisation():
    t = normalize_text("De\u00advel-\nopment ﬁrm\r\nLine\u200b two\r\n• bullet")
    assert "Development firm" in t and "Line two" in t and "bullet" in t and "•" not in t


def test_two_column_pdf_is_read_column_by_column(samples):
    ex, p, q = _parse(samples, "two_column.pdf")
    assert ex.multi_column_pages == [1]
    assert p["name"] == "Amara Okonkwo"
    assert [r["company"] for r in p["experience"]] == ["Ledgerline", "Quayside Tech"]
    assert {"Java", "Kafka", "Kubernetes"} <= set(p["technical_skills"])
    assert p["linkedin"] == "https://www.linkedin.com/in/amara-okonkwo-demo"
    assert q["level"] == "high"


@needs_ocr
def test_scanned_pdf_is_ocrd(samples):
    ex, p, q = _parse(samples, "scanned.pdf")
    assert ex.ocr_pages == [1] and ex.method == "ocr"
    assert p["name"] == "Ravi Shankar" and p["email"] == "ravi.shankar@example.com"
    assert p["phone_e164"] == "+919845055507"
    assert len(p["experience"]) == 2
    assert any(c["id"] == "ocr" and c["status"] == "warn" for c in q["checks"])


def test_contact_details_in_docx_header_and_hyperlinks(samples):
    _, p, _ = _parse(samples, "header_contact.docx")
    assert p["name"] == "Jonas Lindqvist" and p["field_sources"]["name"] == "header"
    assert p["phone_e164"] == "+46555123456"
    assert p["github"] == "https://github.com/jonas-lindqvist-demo"
    assert p["education"][0]["institution"] == "KTH Royal Institute of Technology"


@needs_office
@pytest.mark.parametrize("name", ["legacy.doc", "resume.rtf", "resume.odt"])
def test_legacy_formats_match_the_docx_parse(samples, name):
    _, ref, _ = _parse(samples, "header_contact.docx")
    _, p, _ = _parse(samples, name)
    for key in ("name", "email", "phone_e164", "linkedin", "total_years", "technical_skills"):
        assert p[key] == ref[key], key


def test_tricky_dates_overlaps_and_gaps(samples):
    _, p, q = _parse(samples, "tricky_dates.txt")
    dates = {r["date_text"]: (r["start"], r["end"]) for r in p["experience"]}
    assert dates["Since March 2022"] == ("2022-03-01", "2026-11-01")
    assert dates["Jan '19 – Feb '22"] == ("2019-01-01", "2022-02-01")
    assert dates["06/2015 to 08/2017"] == ("2015-06-01", "2017-08-01")
    assert p["overlap_months"] == 24
    assert p["total_years"] == 10.2
    assert p["employment_gaps"][0]["months"] >= 12
    assert p["education"][0]["gpa"] == "3.8/4.0"
    assert any(c["id"] == "years_consistency" and c["status"] == "warn" for c in q["checks"])


def test_skill_names_are_never_names_or_locations():
    p = parse_resume("Spring Boot\nPostgreSQL, Spring Boot\nExperience\nDeveloper | X | 2020 - 2022\n",
                     "jane_doe_resume.pdf", today=TODAY)
    assert p["name"] != "Spring Boot" and p["location"] != "PostgreSQL, Spring Boot"


def test_low_quality_parse_is_flagged():
    p = parse_resume("Some text without much structure at all here.", "file.pdf", today=TODAY)
    q = assess(p, {"warnings": [], "ocr_pages": []})
    assert q["level"] == "low" and any("No dated work history" in i for i in q["issues"])
