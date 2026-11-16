"""Backwards-compatible facade over the ingestion package (app/ingest)."""

from __future__ import annotations

from ..ingest.detect import EXTENSIONS as SUPPORTED_EXTENSIONS
from ..ingest.detect import FileRejected
from ..ingest.extractors import Extraction, extract, normalize_text

UnsupportedFileError = FileRejected  # old name kept for callers/tests

__all__ = ["SUPPORTED_EXTENSIONS", "Extraction", "UnsupportedFileError", "extract", "extract_text", "normalize_text"]


def extract_text(filename: str, data: bytes) -> str:
    return extract(filename, data).text
