"""Structured logging.

* JSON lines in production (one object per event, ready for Loki/ELK/CloudWatch),
  human-readable text in development.
* Every record carries the current request id and actor (from context vars set
  by the request middleware), so all logs of one request can be correlated.
* PII redaction: resumes are full of personal data. Emails and phone numbers are
  masked in every log message and string field before it leaves the process.
"""

from __future__ import annotations

import contextvars
import logging
import re
import sys

from pythonjsonlogger.json import JsonFormatter

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
actor_var: contextvars.ContextVar[str] = contextvars.ContextVar("actor", default="system")

_EMAIL = re.compile(r"([\w.+-])[\w.+-]*@([\w-]+\.)+[\w-]+")
_PHONE = re.compile(r"(?<![\w/])\+?\d[\d\s().-]{7,}\d(?![\w/])")
_STANDARD_ATTRS = set(vars(logging.makeLogRecord({}))) | {"message", "asctime", "taskName"}


def redact(value: str) -> str:
    """Mask emails (a***@***) and phone-like digit runs (***-**42)."""
    value = _EMAIL.sub(lambda m: f"{m.group(1)}***@***", value)
    def _mask_phone(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group())
        return "***" + digits[-2:] if len(digits) >= 9 else m.group()

    return _PHONE.sub(_mask_phone, value)


class ContextFilter(logging.Filter):
    """Attach request context and redact PII on every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.actor = actor_var.get()
        if record.args:
            try:
                record.msg = record.getMessage()
                record.args = None
            except Exception:  # noqa: BLE001 - never let logging crash the app
                pass
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        for key, val in list(vars(record).items()):
            if key not in _STANDARD_ATTRS and isinstance(val, str):
                setattr(record, key, redact(val))
        return True


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = {k: v for k, v in vars(record).items()
                  if k not in _STANDARD_ATTRS and k not in {"request_id", "actor"}}
        tail = " ".join(f"{k}={v}" for k, v in extras.items())
        return f"{base} {tail}".rstrip()


def setup_logging(level: str = "INFO", json_logs: bool = False) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(ContextFilter())
    if json_logs:
        handler.setFormatter(JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(actor)s",
            rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
            timestamp=False,
        ))
    else:
        handler.setFormatter(TextFormatter("%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s"))

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers[:] = []
        lg.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
    for noisy in ("httpx", "httpx2", "sentence_transformers", "pdfminer", "urllib3", "filelock", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
