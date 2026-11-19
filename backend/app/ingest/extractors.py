"""Document -> plain text, with provenance.

PDF   pdfplumber text layer; two-column layouts are detected per page and read
      column by column; pages without a usable text layer (scans, outlined
      fonts, "(cid:..)" garbage) are OCR'd with Tesseract. Embedded hyperlinks
      (e.g. a "LinkedIn" label linking to the profile URL) are collected.
DOCX  body in document order (paragraphs + tables), text boxes, headers/footers
      (contact details often live there) and hyperlink targets.
DOC/RTF/ODT  converted to DOCX with LibreOffice (keeps page headers and links),
      falling back to antiword (DOC) or content.xml (ODT).
TXT   BOM / UTF-8 / UTF-16 / cp1252 decoding.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import logging
import re
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from ..config import get_settings
from .detect import FileRejected, sniff

log = logging.getLogger("maxresume.ingest")


@dataclass
class Extraction:
    text: str
    file_type: str
    method: str
    sha256: str
    size_bytes: int
    pages: int | None = None
    pages_processed: int | None = None
    ocr_pages: list[int] = field(default_factory=list)
    multi_column_pages: list[int] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def meta(self) -> dict:
        d = asdict(self)
        d.pop("text")
        return d



def extract(filename: str, data: bytes) -> Extraction:
    kind, warnings = sniff(data, filename)
    handler = {"pdf": _pdf, "docx": _docx, "odt": _odt, "doc": _doc, "rtf": _rtf, "txt": _txt}[kind]
    ex = handler(data)
    ex.file_type = kind
    ex.sha256 = hashlib.sha256(data).hexdigest()
    ex.size_bytes = len(data)
    ex.warnings = warnings + ex.warnings
    ex.text = normalize_text(ex.text)
    ex.links = list(dict.fromkeys(ex.links))
    if len(re.sub(r"\W", "", ex.text)) < 30:
        if kind == "pdf" and not ex.ocr_pages:
            reason = ("This PDF appears to be a scanned image and OCR is unavailable on the server."
                      if not _ocr_available() else "No readable text found in this PDF.")
        else:
            reason = "No readable text found in this file."
        raise FileRejected("no_text", reason)
    return ex



def _ocr_available() -> bool:
    return get_settings().ocr_enabled and shutil.which("tesseract") is not None


def _garbled(text: str) -> bool:
    """Text layer exists but is unusable (unmapped glyphs / private-use chars)."""
    if not text:
        return False
    cid = len(re.findall(r"\(cid:\d+\)", text))
    pua = sum(1 for ch in text if 0xE000 <= ord(ch) <= 0xF8FF)
    tokens = max(1, len(text.split()))
    return cid / tokens > 0.3 or pua / max(1, len(text)) > 0.2


def _find_gutter(words: list[dict], width: float) -> float | None:
    """x-position of a vertical gutter separating two text columns, if any.

    A gutter is an empty vertical band (no word crosses it on almost every line)
    in the middle half of the page, with substantial text on both sides that sits
    side-by-side on the same lines.
    """
    if len(words) < 40:
        return None
    n = len(words)
    lines = {round(w["top"] / 3) for w in words}
    tolerance = max(2, int(0.04 * len(lines)))
    best_run, run_start = (0.0, None), None
    xs = [x / 2 for x in range(int(width * 0.25 * 2), int(width * 0.75 * 2))]
    for x in xs + [None]:
        ok = False
        if x is not None:
            crossing = sum(1 for w in words if w["x0"] < x < w["x1"])
            ok = crossing <= tolerance
        if ok and run_start is None:
            run_start = x
        elif not ok and run_start is not None:
            end = xs[xs.index(x) - 1] if x is not None else xs[-1]
            if end - run_start > best_run[0]:
                best_run = (end - run_start, (run_start + end) / 2)
            run_start = None
    gap, mid = best_run
    if mid is None or gap < 6:
        return None
    left = [w for w in words if w["x1"] <= mid]
    right = [w for w in words if w["x0"] >= mid]
    if len(left) < 0.15 * n or len(right) < 0.15 * n:
        return None
    both = {round(w["top"] / 3) for w in left} & {round(w["top"] / 3) for w in right}
    return mid if len(both) >= 5 else None


def _words_to_lines(words: list[dict]) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(lines[-1][0]["top"] - w["top"]) <= 3:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def _line_text(ws: list[dict]) -> str:
    out, prev = "", None
    for w in ws:
        if prev is not None:
            gap = w["x0"] - prev["x1"]
            char_w = (prev["x1"] - prev["x0"]) / max(1, len(prev["text"]))
            out += "    " if gap > 3 * char_w else " "
        out += w["text"]
        prev = w
    return out


def _two_column_text(words: list[dict], gutter: float) -> str:
    """Read left column then right column; full-width lines (headings, name) stay in place."""
    out: list[str] = []
    left_buf: list[str] = []
    right_buf: list[str] = []

    def flush():
        out.extend(left_buf)
        out.extend(right_buf)
        left_buf.clear()
        right_buf.clear()

    for line in _words_to_lines(words):
        if any(w["x0"] < gutter < w["x1"] for w in line):
            flush()
            out.append(_line_text(line))
            continue
        left = [w for w in line if w["x1"] <= gutter]
        right = [w for w in line if w["x0"] >= gutter]
        if left:
            left_buf.append(_line_text(left))
        if right:
            right_buf.append(_line_text(right))
    flush()
    return "\n".join(out)


def _is_password_error(e: BaseException) -> bool:
    seen = 0
    while e is not None and seen < 5:
        if "Password" in type(e).__name__ or "password" in str(e).lower() or \
                any("Password" in type(a).__name__ for a in getattr(e, "args", ())):
            return True
        e, seen = e.__cause__ or e.__context__, seen + 1
    return False


def _ocr_page(page) -> str:
    import pytesseract

    s = get_settings()
    img = page.to_image(resolution=s.ocr_dpi).original
    return pytesseract.image_to_string(img, lang="eng", config="--psm 3", timeout=30)


def _pdf(data: bytes) -> Extraction:
    import pdfplumber

    s = get_settings()
    ex = Extraction(text="", file_type="pdf", method="pdf-text", sha256="", size_bytes=0)

    def reject(e: Exception):
        if _is_password_error(e):
            raise FileRejected("encrypted", "This PDF is password-protected. Upload an unlocked copy.") from e
        raise FileRejected("corrupt", "This PDF is damaged or not a valid PDF.") from e

    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except Exception as e:  # noqa: BLE001 - any parser failure means unreadable
        reject(e)

    texts: list[str] = []
    with pdf:
        try:
            pages = pdf.pages
        except Exception as e:  # noqa: BLE001
            reject(e)
        ex.pages = len(pages)
        if ex.pages > s.max_pdf_pages:
            ex.warnings.append(f"Document has {ex.pages} pages; only the first {s.max_pdf_pages} were read.")
        ocr_budget = s.ocr_max_pages if _ocr_available() else 0
        for i, page in enumerate(pages[: s.max_pdf_pages], start=1):
            with contextlib.suppress(Exception):
                ex.links += [h.get("uri") for h in (page.hyperlinks or []) if h.get("uri")]
            words = page.extract_words(x_tolerance=1.5, y_tolerance=3) or []
            gutter = _find_gutter(words, float(page.width))
            if gutter:
                ex.multi_column_pages.append(i)
                text = _two_column_text(words, gutter)
            else:
                text = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
            if (len(text.strip()) < 40 or _garbled(text)) and (page.images or not text.strip() or _garbled(text)):
                if ocr_budget > 0:
                    try:
                        text = _ocr_page(page)
                        ex.ocr_pages.append(i)
                        ocr_budget -= 1
                    except Exception as e:  # noqa: BLE001
                        log.warning("OCR failed on page %s", i, extra={"error": str(e)})
                        ex.warnings.append(f"OCR failed on page {i}.")
                elif page.images:
                    ex.warnings.append(f"Page {i} looks like a scanned image and could not be OCR'd.")
            texts.append(text)
        ex.pages_processed = min(ex.pages, s.max_pdf_pages)
    if ex.ocr_pages:
        ex.method = "ocr" if len(ex.ocr_pages) == ex.pages_processed else "pdf-text+ocr"
        ex.warnings.append(f"OCR was used on page(s) {', '.join(map(str, ex.ocr_pages))}; "
                           f"recognition errors are possible, please verify key details.")
    if ex.multi_column_pages:
        ex.method += "+columns"
    ex.text = "\n".join(texts)
    return ex



_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx(data: bytes) -> Extraction:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    ex = Extraction(text="", file_type="docx", method="docx", sha256="", size_bytes=0)
    try:
        doc = Document(io.BytesIO(data))
    except Exception as e:  # noqa: BLE001
        raise FileRejected("corrupt", "This Word document is damaged and could not be opened.") from e

    lines: list[str] = []

    def textboxes(el) -> list[str]:
        return ["".join(t.text or "" for t in p.iter(f"{_W}t"))
                for box in el.iter(f"{_W}txbxContent") for p in box.iter(f"{_W}p")]

    def table_lines(tbl) -> list[str]:
        out = []
        for row in tbl.rows:
            seen, cells = set(), []
            for cell in row.cells:
                if id(cell._tc) in seen:
                    continue
                seen.add(id(cell._tc))
                if cell.text.strip():
                    cells.append(cell.text.strip())
                for nested in cell.tables:
                    out += table_lines(nested)
            out.append(" | ".join(cells))
        return out

    header_seen = set()
    for section in doc.sections:
        for part in (section.header, section.first_page_header):
            try:
                for p in part.paragraphs:
                    if p.text.strip() and p.text not in header_seen:
                        header_seen.add(p.text)
                        lines.append(p.text)
                for t in part.tables:
                    lines += table_lines(t)
            except Exception:  # noqa: BLE001 - missing header parts are fine
                continue

    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            lines.append(Paragraph(child, doc).text)
            lines += textboxes(child)
        elif tag == "tbl":
            lines += table_lines(Table(child, doc))

    for section in doc.sections:
        try:
            for p in section.footer.paragraphs:
                if p.text.strip():
                    lines.append(p.text)
        except Exception:  # noqa: BLE001
            continue

    parts = [doc.part]
    for section in doc.sections:
        for hf in (section.header, section.first_page_header, section.footer):
            try:
                parts.append(hf.part)
            except Exception:  # noqa: BLE001 - part may not exist
                continue
    for part in parts:
        try:
            ex.links += [r.target_ref for r in part.rels.values() if r.reltype.endswith("/hyperlink")]
        except Exception:  # noqa: BLE001
            continue
    ex.text = "\n".join(lines)
    return ex



def _odt(data: bytes) -> Extraction:
    converted = _via_docx(data, "odt")
    if converted:
        return converted
    ex = Extraction(text="", file_type="odt", method="odt", sha256="", size_bytes=0)
    try:
        root = ET.fromstring(zipfile.ZipFile(io.BytesIO(data)).read("content.xml"))
    except Exception as e:  # noqa: BLE001
        raise FileRejected("corrupt", "This ODT document is damaged and could not be opened.") from e
    ns_text = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
    ns_xlink = "{http://www.w3.org/1999/xlink}"
    lines = ["".join(el.itertext()) for el in root.iter() if el.tag in (f"{ns_text}p", f"{ns_text}h")]
    ex.links = [a.get(f"{ns_xlink}href") for a in root.iter(f"{ns_text}a") if a.get(f"{ns_xlink}href")]
    ex.text = "\n".join(lines)
    return ex



def _run(cmd: list[str]) -> str:
    s = get_settings()
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=s.converter_timeout_s, check=False)
    except subprocess.TimeoutExpired as e:
        raise FileRejected("timeout", "Converting this document took too long.") from e
    if res.returncode != 0:
        raise RuntimeError(res.stderr.decode(errors="ignore")[:300])
    return res.stdout.decode("utf-8", errors="ignore")


def _libreoffice_convert(data: bytes, suffix: str, target: str) -> bytes | None:
    """Convert with LibreOffice (headless). Returns the converted bytes, or None if unavailable."""
    office = shutil.which("soffice") or shutil.which("libreoffice")
    if not office:
        return None
    with tempfile.TemporaryDirectory(prefix="maxresume-") as tmp:
        src = Path(tmp) / f"input.{suffix}"
        src.write_bytes(data)
        _run([office, f"-env:UserInstallation=file://{tmp}/profile", "--headless", "--convert-to", target,
              "--outdir", tmp, str(src)])
        out = Path(tmp) / f"input.{target.split(':')[0]}"
        return out.read_bytes() if out.exists() else None


def _via_docx(data: bytes, suffix: str) -> Extraction | None:
    """Legacy formats -> DOCX -> our DOCX extractor, which keeps page headers and hyperlinks
    (plain-text converters silently drop headers, where contact details usually live)."""
    try:
        converted = _libreoffice_convert(data, suffix, "docx")
    except (RuntimeError, FileRejected) as e:
        log.warning("LibreOffice conversion failed", extra={"format": suffix, "error": str(e)[:200]})
        return None
    if not converted:
        return None
    ex = _docx(converted)
    ex.method = "libreoffice->docx"
    return ex


def _doc(data: bytes) -> Extraction:
    ex = _via_docx(data, "doc")
    if ex:
        return ex
    ex = Extraction(text="", file_type="doc", method="antiword", sha256="", size_bytes=0)
    if shutil.which("antiword"):
        with tempfile.NamedTemporaryFile(suffix=".doc") as f:
            f.write(data)
            f.flush()
            try:
                ex.text = _run(["antiword", "-w", "0", f.name])
                return ex
            except RuntimeError:
                pass
    raise FileRejected("unsupported", "Legacy .doc files need LibreOffice or antiword on the server. "
                                      "Please upload PDF or DOCX.")


def _rtf(data: bytes) -> Extraction:
    ex = _via_docx(data, "rtf")
    if ex:
        return ex
    raise FileRejected("unsupported", "RTF files need LibreOffice on the server. Please upload PDF or DOCX.")



def _txt(data: bytes) -> Extraction:
    ex = Extraction(text="", file_type="txt", method="plain", sha256="", size_bytes=0)
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        ex.text = data.decode("utf-16", errors="ignore")
    else:
        try:
            ex.text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            ex.text = data.decode("cp1252", errors="replace")
            ex.warnings.append("Text file was not UTF-8; decoded as Windows-1252.")
    return ex



_BULLETS = re.compile(r"^[\s]*[•●▪◦‣∙·\-\*–—►✓➢❖■□➤→]+\s*", re.MULTILINE)
_CONTROL = re.compile("[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f\\u00ad\\u200b-\\u200f\\u2028\\u2029\\ufeff]")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ").replace("\f", "\n")
    text = re.sub(r"\(cid:\d+\)", "", text)
    text = _CONTROL.sub("", text)
    text = re.sub(r"([a-z])-\n([a-z])", r"\1\2", text)
    text = _BULLETS.sub("", text)
    text = re.sub(r"[  ]{5,}", "    ", text)
    text = re.sub(r"(?<! )[  ]{2,3}(?! )", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()
