"""Append-only, tamper-evident audit trail.

Every state-changing action (and every access to candidate personal data) is
recorded with who did it, when, from which request, and what changed.

Tamper evidence: entries form a hash chain. Each entry stores the SHA-256 of
its own canonical content *including the previous entry's hash*, so editing or
deleting any historical entry breaks every hash after it. `verify()` walks the
chain and reports the first broken link.

Concurrency: `seq` has a unique index; if two writers race for the same
sequence number the loser reloads the chain head and retries.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from .db import DuplicateKey
from .logging_setup import actor_var, request_id_var

log = logging.getLogger("maxresume.audit")

GENESIS = "0" * 64
HASHED_FIELDS = ("seq", "ts", "actor", "request_id", "action", "outcome", "target_type", "target_id",
                 "job_id", "details", "prev_hash")


def _canonical(entry: dict) -> bytes:
    return json.dumps({k: entry.get(k) for k in HASHED_FIELDS}, sort_keys=True, separators=(",", ":"),
                      default=str).encode()


def entry_hash(entry: dict) -> str:
    return hashlib.sha256(_canonical(entry)).hexdigest()


class AuditLog:
    def __init__(self, store) -> None:
        self.store = store
        self._lock = asyncio.Lock()
        self._head: tuple[int, str] | None = None

    async def _load_head(self) -> tuple[int, str]:
        last = await self.store.find("audit_log", {}, {"seq": 1, "hash": 1}, sort=[("seq", -1)], limit=1)
        return (last[0]["seq"], last[0]["hash"]) if last else (0, GENESIS)

    async def record(self, action: str, *, target_type: str | None = None, target_id: str | None = None,
                     job_id: str | None = None, details: dict[str, Any] | None = None,
                     outcome: str = "success") -> dict:
        async with self._lock:
            for attempt in range(5):
                if self._head is None or attempt:
                    self._head = await self._load_head()
                seq, prev = self._head
                entry = {
                    "_id": uuid.uuid4().hex,
                    "seq": seq + 1,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "actor": actor_var.get(),
                    "request_id": request_id_var.get(),
                    "action": action,
                    "outcome": outcome,
                    "target_type": target_type,
                    "target_id": target_id,
                    "job_id": job_id,
                    "details": details or {},
                    "prev_hash": prev,
                }
                entry["hash"] = entry_hash(entry)
                try:
                    await self.store.insert("audit_log", entry)
                except DuplicateKey:
                    continue
                self._head = (entry["seq"], entry["hash"])
                log.info("audit %s", action, extra={"audit_action": action, "audit_seq": entry["seq"],
                                                    "target_type": target_type, "target_id": target_id,
                                                    "outcome": outcome})
                return entry
            raise RuntimeError("Could not append to audit log after retries")

    async def list(self, *, job_id: str | None = None, action: str | None = None, actor: str | None = None,
                   since: str | None = None, limit: int = 200) -> list[dict]:
        q: dict[str, Any] = {}
        if job_id:
            q["job_id"] = job_id
        if action:
            q["action"] = action
        if actor:
            q["actor"] = actor
        if since:
            q["ts"] = {"$gte": since}
        return await self.store.find("audit_log", q, sort=[("seq", -1)], limit=min(limit, 1000))

    async def verify(self) -> dict:
        """Recompute the whole chain. Returns ok + the first inconsistency, if any."""
        entries = await self.store.find("audit_log", {}, sort=[("seq", 1)])
        prev, expected_seq = GENESIS, 1
        for e in entries:
            if e["seq"] != expected_seq:
                return {"ok": False, "entries": len(entries), "broken_at_seq": expected_seq,
                        "reason": f"missing entry: expected seq {expected_seq}, found {e['seq']}"}
            if e["prev_hash"] != prev:
                return {"ok": False, "entries": len(entries), "broken_at_seq": e["seq"],
                        "reason": "previous-hash link does not match (an earlier entry was altered or removed)"}
            if entry_hash(e) != e["hash"]:
                return {"ok": False, "entries": len(entries), "broken_at_seq": e["seq"],
                        "reason": "entry content does not match its hash (entry was modified)"}
            prev, expected_seq = e["hash"], expected_seq + 1
        return {"ok": True, "entries": len(entries), "head_hash": prev}


def public_entry(e: dict) -> dict:
    return {k: e.get(k) for k in ("seq", "ts", "actor", "request_id", "action", "outcome", "target_type",
                                  "target_id", "job_id", "details", "hash", "prev_hash")}
