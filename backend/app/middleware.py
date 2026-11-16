"""Request middleware (pure ASGI, so streaming responses are untouched).

For every HTTP request:
  * assigns a request id (honours a well-formed incoming X-Request-ID) and echoes it back
  * resolves the actor: API key -> name when keys are configured (401 otherwise)
  * adds security headers
  * writes one structured access-log line with status and latency
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid

from .config import get_settings
from .logging_setup import actor_var, request_id_var

log = logging.getLogger("maxresume.access")

_VALID_RID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
PUBLIC_PATHS = {"/api/health", "/api/ready", "/docs", "/openapi.json", "/redoc"}
_BASE_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
]


def security_headers(path: str) -> list[tuple[bytes, bytes]]:
    headers = list(_BASE_HEADERS)
    ancestors = get_settings().frame_ancestors.strip()
    if ancestors:  # e.g. hosted inside the Hugging Face Spaces page
        headers.append((b"content-security-policy", f"frame-ancestors 'self' {ancestors}".encode()))
    else:
        headers.append((b"x-frame-options", b"DENY"))
    if path.startswith("/api"):
        headers.append((b"cache-control", b"no-store"))  # API responses may contain personal data
    return headers


class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = {k.decode().lower(): v.decode(errors="ignore") for k, v in scope.get("headers", [])}
        incoming = headers.get("x-request-id", "")
        rid = incoming if _VALID_RID.match(incoming) else uuid.uuid4().hex[:16]
        rid_token = request_id_var.set(rid)

        keys = get_settings().api_key_map
        path = scope.get("path", "")
        if keys:
            actor = keys.get(headers.get("x-api-key", ""))
        else:
            actor = "local-user"  # auth disabled: single-user local deployment
        actor_token = actor_var.set(actor or "unauthenticated")

        start = time.perf_counter()
        status = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                message["headers"] = (list(message.get("headers", [])) + [(b"x-request-id", rid.encode())]
                                      + security_headers(path))
            await send(message)

        try:
            if keys and actor is None and path.startswith("/api") and path not in PUBLIC_PATHS \
                    and scope.get("method") != "OPTIONS":
                body = json.dumps({"detail": "Missing or invalid API key",
                                   "error": {"code": "unauthorized", "message": "Missing or invalid API key",
                                             "request_id": rid}}).encode()
                await send_wrapper({"type": "http.response.start", "status": 401,
                                    "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": body})
                return
            await self.app(scope, receive, send_wrapper)
        finally:
            if path.startswith("/api") and path not in {"/api/health", "/api/ready"}:
                level = logging.WARNING if status["code"] >= 500 else logging.INFO
                log.log(level, "%s %s %s", scope.get("method"), path, status["code"],
                        extra={"http_method": scope.get("method"), "path": path, "status": status["code"],
                               "duration_ms": round((time.perf_counter() - start) * 1000, 1)})
            request_id_var.reset(rid_token)
            actor_var.reset(actor_token)
