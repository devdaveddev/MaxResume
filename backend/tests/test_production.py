"""Operational behaviour: audit trail, logging, request ids, auth, error format, CSV safety."""

import asyncio
import logging

import pytest
from fastapi.testclient import TestClient

from app.audit import AuditLog, entry_hash
from app.config import get_settings
from app.db import MemoryStore
from app.logging_setup import ContextFilter, redact
from app.main import _csv_safe, _safe_filename, app

JD = ("Backend Engineer\nRequirements\n3+ years of experience with Java and Spring Boot.\n"
      "Experience with PostgreSQL and Docker.\n")


# ---------------------------------------------------------------- audit chain
def test_audit_chain_detects_tampering():
    async def run():
        s = MemoryStore()
        a = AuditLog(s)
        for i in range(5):
            await a.record("job.created", target_id=f"j{i}", details={"i": i})
        assert (await a.verify())["ok"]

        # modify an entry's details in place
        e = (await s.find("audit_log", {"seq": 3}))[0]
        s._c["audit_log"][e["_id"]]["details"] = {"i": 999}
        bad = await a.verify()
        assert not bad["ok"] and bad["broken_at_seq"] == 3

        # restore, then delete an entry
        s._c["audit_log"][e["_id"]]["details"] = {"i": 2}
        assert (await a.verify())["ok"]
        del s._c["audit_log"][e["_id"]]
        assert not (await a.verify())["ok"]

    asyncio.run(run())


def test_audit_hash_covers_previous_entry():
    async def run():
        a = AuditLog(MemoryStore())
        e1 = await a.record("x")
        e2 = await a.record("y")
        assert e2["prev_hash"] == e1["hash"] and entry_hash(e2) == e2["hash"]

    asyncio.run(run())


def test_api_actions_are_audited_and_chain_verifies(samples):
    with TestClient(app) as c:
        job = c.post("/api/jobs", data={"text": JD}).json()
        files = [("files", (p.name, p.read_bytes())) for p in sorted((samples / "resumes").iterdir())[:3]]
        files.append(("files", ("photo.pdf", (samples / "edge_cases" / "renamed_image.pdf").read_bytes())))
        res = c.post(f"/api/jobs/{job['id']}/resumes", files=files).json()
        cand = res["added"][0]["id"]
        c.get(f"/api/candidates/{cand}")
        c.put(f"/api/jobs/{job['id']}", json={"min_years": 6, "required_skills": ["Java", "Kafka"]})
        c.get(f"/api/jobs/{job['id']}/export.csv")

        log = c.get("/api/audit", params={"job_id": job["id"]}).json()
        actions = [e["action"] for e in log]
        assert {"job.created", "resume.ingested", "resume.rejected", "candidate.viewed", "job.updated",
                "ranking.exported"} <= set(actions)
        upd = next(e for e in log if e["action"] == "job.updated")
        assert upd["details"]["changes"]["min_years"] == {"from": 3.0, "to": 6}
        assert "Kafka" in upd["details"]["changes"]["required_skills"]["added"]
        assert all(e["actor"] == "local-user" and e["request_id"] != "-" for e in log)
        rejected = next(e for e in log if e["action"] == "resume.rejected")
        assert rejected["details"]["code"] == "unsupported" and len(rejected["details"]["sha256"]) == 64

        v = c.get("/api/audit/verify").json()
        assert v["ok"] and v["entries"] >= len(log)


# ---------------------------------------------------------------- logging
def test_pii_is_redacted_in_logs():
    assert redact("mail jane.doe@acme.com or call +91 98765 43210") == "mail j***@*** or call ***10"
    assert redact("parsed 2026-11-16 in 340 ms") == "parsed 2026-11-16 in 340 ms"  # dates/numbers untouched
    rec = logging.makeLogRecord({"msg": "candidate %s", "args": ("bob@x.io",), "levelno": 20})
    rec.upload = "call 415 555 0132"
    ContextFilter().filter(rec)
    assert "bob@x.io" not in rec.msg and "555 0132" not in rec.upload


def test_request_id_is_generated_and_propagated():
    with TestClient(app) as c:
        r = c.get("/api/health")
        assert len(r.headers["x-request-id"]) >= 8
        r = c.get("/api/health", headers={"X-Request-ID": "trace-abc-12345"})
        assert r.headers["x-request-id"] == "trace-abc-12345"
        assert r.headers["x-content-type-options"] == "nosniff"


# ---------------------------------------------------------------- auth
def test_api_key_auth(monkeypatch):
    monkeypatch.setattr(get_settings(), "api_keys", "alice:k-alice-123")
    with TestClient(app) as c:
        assert c.get("/api/jobs").status_code == 401
        assert c.get("/api/health").status_code == 200  # liveness stays public
        assert c.get("/api/jobs", headers={"X-API-Key": "k-alice-123"}).status_code == 200
        job = c.post("/api/jobs", data={"text": JD}, headers={"X-API-Key": "k-alice-123"}).json()
        log = c.get("/api/audit", params={"job_id": job["id"]}, headers={"X-API-Key": "k-alice-123"}).json()
        assert log[0]["actor"] == "alice"


# ---------------------------------------------------------------- errors & input safety
def test_consistent_error_shape():
    with TestClient(app) as c:
        r = c.get("/api/jobs/does-not-exist")
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found" and r.json()["error"]["request_id"]
        job = c.post("/api/jobs", data={"text": JD}).json()
        r = c.put(f"/api/jobs/{job['id']}", json={"weights": {"vibes": 1}})
        assert r.status_code == 422 and r.json()["error"]["fields"]


@pytest.mark.parametrize("raw,safe", [("../../etc/passwd", "passwd"), ("C:\\Users\\x\\cv.pdf", "cv.pdf"),
                                      ('evil"\r\n.pdf', "evil.pdf"), ("", "resume")])
def test_filename_sanitisation(raw, safe):
    assert _safe_filename(raw) == safe


def test_csv_formula_injection_is_neutralised():
    assert _csv_safe("=HYPERLINK(\"http://x\")").startswith("'=")
    assert _csv_safe("+1 555") == "'+1 555" and _csv_safe("Alice") == "Alice"
