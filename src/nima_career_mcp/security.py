"""ASGI middleware enforcing the public server's safety posture.

These are the server-side measures the MCP spec calls for on a public HTTP server:
  * per-IP rate limiting (Tools security: "rate limit tool invocations"),
  * request body-size caps (input validation / DoS resistance),
  * Origin validation (Streamable HTTP transport: DNS-rebinding defense).

They are written as raw ASGI middleware (not BaseHTTPMiddleware) so they never buffer or
break streaming responses. Behavioral guardrails (honesty / prompt-injection refusal) live
in the *consuming host's* system prompt, served from the `career://guidance` resource — not
here. This layer only decides whether to let a request reach the MCP app.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque

from starlette.types import ASGIApp, Receive, Scope, Send


async def _send_error(send: Send, status: int, detail: str) -> None:
    body = json.dumps({"error": detail}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _client_ip(scope: Scope) -> str:
    # Honor X-Forwarded-For when behind a proxy (Fly), else fall back to the socket peer.
    for name, value in scope.get("headers", []):
        if name == b"x-forwarded-for":
            return value.decode().split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


class RateLimitMiddleware:
    """Fixed-window per-IP rate limit."""

    def __init__(self, app: ASGIApp, limit_per_min: int = 60) -> None:
        self.app = app
        self.limit = limit_per_min
        self.window = 60.0
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.limit <= 0:
            await self.app(scope, receive, send)
            return

        ip = _client_ip(scope)
        now = time.monotonic()
        q = self._hits[ip]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            await _send_error(send, 429, "Rate limit exceeded. Try again shortly.")
            return
        q.append(now)
        await self.app(scope, receive, send)


class BodySizeLimitMiddleware:
    """Reject requests whose declared body exceeds `max_bytes`."""

    def __init__(self, app: ASGIApp, max_bytes: int = 256 * 1024) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    if int(value) > self.max_bytes:
                        await _send_error(send, 413, "Request body too large.")
                        return
                except ValueError:
                    pass
        await self.app(scope, receive, send)


class OriginValidationMiddleware:
    """Validate the Origin header against an allowlist (DNS-rebinding defense).

    If `allowed_origins` is empty, all origins are allowed (intentionally public server),
    but non-browser clients (no Origin header) always pass. Set NIMA_ALLOWED_ORIGINS to
    restrict browser callers to your website origin(s).
    """

    def __init__(self, app: ASGIApp, allowed_origins: list[str] | None = None) -> None:
        self.app = app
        self.allowed = {o.strip() for o in (allowed_origins or []) if o.strip()}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.allowed:
            await self.app(scope, receive, send)
            return
        origin: str | None = None
        for name, value in scope.get("headers", []):
            if name == b"origin":
                origin = value.decode()
                break
        # No Origin header => non-browser agent (Claude Code, backend client) => allow.
        if origin is None or origin in self.allowed:
            await self.app(scope, receive, send)
            return
        await _send_error(send, 403, "Origin not allowed.")


class HostValidationMiddleware:
    """Validate the Host header against an allowlist (DNS-rebinding defense).

    The MCP SDK ships its own Host check but only auto-enables it for localhost binds, where
    it then 421s any real deployed hostname. We disable the SDK's copy (see server.py) and
    own the policy here so it follows the same "empty allowlist = public" semantics as the
    rest of this layer: with NIMA_ALLOWED_HOSTS unset, any Host passes (intentionally public
    server). Set NIMA_ALLOWED_HOSTS to your deploy hostname(s) to lock it down — e.g.
    `nima-career-mcp.fly.dev`. A trailing `:*` allows any port (e.g. `localhost:*`).
    """

    def __init__(self, app: ASGIApp, allowed_hosts: list[str] | None = None) -> None:
        self.app = app
        self.allowed = {h.strip() for h in (allowed_hosts or []) if h.strip()}

    def _ok(self, host: str) -> bool:
        if host in self.allowed:
            return True
        # Wildcard-port patterns: "example.com:*" matches "example.com:8080".
        for pattern in self.allowed:
            if pattern.endswith(":*") and host.startswith(pattern[:-1]):
                return True
        return False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.allowed:
            await self.app(scope, receive, send)
            return
        host: str | None = None
        for name, value in scope.get("headers", []):
            if name == b"host":
                host = value.decode()
                break
        if host is not None and self._ok(host):
            await self.app(scope, receive, send)
            return
        await _send_error(send, 421, "Host not allowed.")
