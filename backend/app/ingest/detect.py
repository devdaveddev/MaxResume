"""File-type detection and safety checks, done on the bytes, never trusting the filename.

* Type is sniffed from magic bytes (and, for ZIP containers, from the entries).
  A mismatch with the extension is allowed but reported as a warning.
* Zip containers (DOCX/ODT) are checked for zip bombs before anything opens them.
* Anything we don't recognise as a document (executables, images, archives) is rejected.
"""

from __future__ import annotations

import io
import zipfile

from ..config import get_settings


class FileRejected(ValueError):
    """The file cannot be processed. `code` is a stable machine-readable reason."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


SUPPORTED_TYPES = {"pdf", "docx", "doc", "odt", "rtf", "txt"}
EXTENSIONS = {".pdf", ".docx", ".doc", ".odt", ".rtf", ".txt"}
MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "odt": "application/vnd.oasis.opendocument.text",
    "rtf": "application/rtf",
    "txt": "text/plain; charset=utf-8",
}

_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # legacy MS Office compound file
_REJECT_SIGNATURES = {
    b"MZ": "executable", b"\x7fELF": "executable", b"\x89PNG": "image", b"\xff\xd8\xff": "image",
    b"GIF8": "image", b"Rar!": "archive", b"7z\xbc\xaf": "archive", b"\x1f\x8b": "archive",
}


def _check_zip(data: bytes) -> zipfile.ZipFile:
    s = get_settings()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise FileRejected("corrupt", "The file looks like a Word/ODT document but is corrupt.") from e
    infos = zf.infolist()
    total = sum(i.file_size for i in infos)
    if len(infos) > 2000 or total > s.max_unzipped_mb * 1024 * 1024:
        raise FileRejected("zip_bomb", "Document expands to an unsafe size and was rejected.")
    for i in infos:
        if i.compress_size and i.file_size / i.compress_size > 200 and i.file_size > 5 * 1024 * 1024:
            raise FileRejected("zip_bomb", "Document has a suspicious compression ratio and was rejected.")
    return zf


def sniff(data: bytes, filename: str) -> tuple[str, list[str]]:
    """Return (file_type, warnings). Raises FileRejected for unsupported/unsafe content."""
    warnings: list[str] = []
    s = get_settings()
    if not data:
        raise FileRejected("empty", "The file is empty.")
    if len(data) > s.max_file_bytes:
        raise FileRejected("too_large", f"File is larger than {s.max_file_mb:g} MB.")

    head = data[:8]
    if data.lstrip()[:5] == b"%PDF-" or data[:1024].find(b"%PDF-") != -1:
        kind = "pdf"
    elif head[:4] == b"PK\x03\x04":
        names = set(_check_zip(data).namelist())
        if "word/document.xml" in names:
            kind = "docx"
        elif "content.xml" in names and "mimetype" in names:
            kind = "odt"
        else:
            raise FileRejected("unsupported", "ZIP archives are not supported. Upload the resume itself (PDF/DOCX).")
    elif head == _OLE:
        kind = "doc"
    elif data[:5] == b"{\\rtf":
        kind = "rtf"
    else:
        for sig, what in _REJECT_SIGNATURES.items():
            if data.startswith(sig):
                raise FileRejected("unsupported", f"This is an {what}, not a resume document.")
        sample = data[:4096]
        if b"\x00" in sample and not sample.startswith((b"\xff\xfe", b"\xfe\xff")):
            raise FileRejected("unsupported", "Unrecognised binary file. Use PDF, DOCX, DOC, ODT, RTF or TXT.")
        kind = "txt"

    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext and ext != kind and not (ext == "text" and kind == "txt"):
        warnings.append(f"File extension .{ext} does not match its content ({kind.upper()}); processed as {kind.upper()}.")
    return kind, warnings
