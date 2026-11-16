"""Persistence: MongoDB (preferred) with an in-memory fallback.

Collections
  jobs        – JD text + parsed requirements + scoring weights
  candidates  – parsed resume profile + match result for one job
  files       – original uploaded resume bytes (for "view original")
  audit_log   – append-only, hash-chained record of every action (see audit.py)

The in-memory store implements the same interface so the app still runs for a
reviewer who does not have MongoDB installed (data is lost on restart).
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from .config import get_settings

log = logging.getLogger("maxresume.db")


class DuplicateKey(Exception):
    """Raised when a unique index would be violated (used by the audit chain)."""


def _matches(doc: dict, query: dict[str, Any]) -> bool:
    for k, v in query.items():
        val = doc.get(k)
        if isinstance(v, dict) and any(op.startswith("$") for op in v):
            for op, arg in v.items():
                if (op == "$gte" and not (val is not None and val >= arg)) or \
                   (op == "$lte" and not (val is not None and val <= arg)) or \
                   (op == "$in" and val not in arg) or (op == "$ne" and val == arg):
                    return False
        elif val != v:
            return False
    return True


class MemoryStore:
    kind = "memory"

    def __init__(self) -> None:
        self._c: dict[str, dict[str, dict]] = {"jobs": {}, "candidates": {}, "files": {}, "audit_log": {}}

    async def ping(self) -> bool:
        return True

    async def insert(self, coll: str, doc: dict) -> None:
        if coll == "audit_log" and any(d["seq"] == doc["seq"] for d in self._c[coll].values()):
            raise DuplicateKey(f"audit seq {doc['seq']}")
        self._c.setdefault(coll, {})[doc["_id"]] = copy.deepcopy(doc)

    async def get(self, coll: str, _id: str) -> dict | None:
        d = self._c.get(coll, {}).get(_id)
        return copy.deepcopy(d) if d else None

    async def find(self, coll: str, query: dict[str, Any], projection: dict | None = None,
                   sort: list[tuple[str, int]] | None = None, limit: int | None = None) -> list[dict]:
        docs = [d for d in self._c.get(coll, {}).values() if _matches(d, query)]
        for key, direction in reversed(sort or []):
            docs.sort(key=lambda d: (d.get(key) is None, d.get(key)), reverse=direction < 0)
        if limit:
            docs = docs[:limit]
        docs = copy.deepcopy(docs)
        if projection:  # mimic Mongo: inclusion ({"a": 1}) or exclusion ({"a": 0, "b.c": 0})
            include = {k for k, v in projection.items() if v}
            if include:
                docs = [{k: v for k, v in d.items() if k in include or k == "_id"} for d in docs]
            else:
                for d in docs:
                    for path in projection:
                        *parents, leaf = path.split(".")
                        target = d
                        for p in parents:
                            target = target.get(p, {})
                        target.pop(leaf, None)
        return docs

    async def update(self, coll: str, _id: str, fields: dict) -> None:
        if _id in self._c.get(coll, {}):
            self._c[coll][_id].update(copy.deepcopy(fields))

    async def delete(self, coll: str, query: dict[str, Any]) -> int:
        ids = [i for i, d in self._c.get(coll, {}).items() if _matches(d, query)]
        for i in ids:
            del self._c[coll][i]
        return len(ids)

    async def count(self, coll: str, query: dict[str, Any]) -> int:
        return sum(1 for d in self._c.get(coll, {}).values() if _matches(d, query))


class MongoStore:
    kind = "mongodb"

    def __init__(self, client, db_name: str) -> None:
        self.client = client
        self.db = client[db_name]

    async def setup(self) -> None:
        await self.db.candidates.create_index([("job_id", 1), ("match.score", -1)])
        await self.db.candidates.create_index([("job_id", 1), ("text_hash", 1)])
        await self.db.audit_log.create_index("seq", unique=True)
        await self.db.audit_log.create_index([("job_id", 1), ("seq", -1)])
        await self.db.audit_log.create_index([("action", 1), ("ts", -1)])

    async def ping(self) -> bool:
        try:
            await self.client.admin.command("ping")
            return True
        except Exception:  # noqa: BLE001
            return False

    async def insert(self, coll: str, doc: dict) -> None:
        from pymongo.errors import DuplicateKeyError

        try:
            await self.db[coll].insert_one(doc)
        except DuplicateKeyError as e:
            raise DuplicateKey(str(e)) from e

    async def get(self, coll: str, _id: str) -> dict | None:
        return await self.db[coll].find_one({"_id": _id})

    async def find(self, coll: str, query: dict[str, Any], projection: dict | None = None,
                   sort: list[tuple[str, int]] | None = None, limit: int | None = None) -> list[dict]:
        cursor = self.db[coll].find(query, projection)
        if sort:
            cursor = cursor.sort(sort)
        if limit:
            cursor = cursor.limit(limit)
        return await cursor.to_list(length=None)

    async def update(self, coll: str, _id: str, fields: dict) -> None:
        await self.db[coll].update_one({"_id": _id}, {"$set": fields})

    async def delete(self, coll: str, query: dict[str, Any]) -> int:
        return (await self.db[coll].delete_many(query)).deleted_count

    async def count(self, coll: str, query: dict[str, Any]) -> int:
        return await self.db[coll].count_documents(query)


async def create_store():
    s = get_settings()
    if s.storage == "memory":
        log.info("Using in-memory store (STORAGE=memory)")
        return MemoryStore()
    try:
        from pymongo import AsyncMongoClient

        client = AsyncMongoClient(s.mongo_url, serverSelectionTimeoutMS=2000)
        await client.admin.command("ping")
        store = MongoStore(client, s.mongo_db)
        await store.setup()
        log.info("Connected to MongoDB", extra={"db": s.mongo_db})
        return store
    except Exception as exc:  # noqa: BLE001 - any connection problem
        if s.storage == "mongodb":
            raise RuntimeError(f"MongoDB required (STORAGE=mongodb) but unavailable: {exc}") from exc
        log.warning("MongoDB unavailable, falling back to in-memory store", extra={"error": str(exc)})
        return MemoryStore()
