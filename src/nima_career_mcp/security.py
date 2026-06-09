"""Raw ASGI middleware enforcing the public server's safety posture: rate limiting,
body-size caps, and Origin/Host validation. Behavioral guardrails (honesty,
prompt-injection refusal) live in the host's system prompt via `career://guidance`.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque

from starlette.types import ASGIApp, Message, Receive, Scope, Send


async def _send_error(
    send: Send,
    status: int,
    detail: str,
    extra_headers: list[tuple[bytes, bytes]] | None = None,
) -> None:
    body = json.dumps({"error": detail}).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
    ]
    if extra_headers:
        headers.extend(extra_headers)
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


def _client_ip(scope: Scope) -> str:
    # Fly-Client-IP is unforgeable; X-Forwarded-For is client-controllable and must not key
    # the rate limiter (spoofing it bypasses the limit and mints unbounded buckets).
    for name, value in scope.get("headers", []):
        if name == b"fly-client-ip":
            return value.decode().strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


class RateLimitMiddleware:
    """Fixed-window per-IP rate limit. Idle buckets are swept so a flood of distinct keys
    can't grow the in-memory map without bound."""

    def __init__(
        self,
        app: ASGIApp,
        limit_per_min: int = 60,
        max_tracked_ips: int = 50_000,
    ) -> None:
        self.app = app
        self.limit = limit_per_min
        self.window = 60.0
        self.max_tracked_ips = max_tracked_ips
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_sweep = 0.0

    def _sweep(self, now: float) -> None:
        stale = [
            ip for ip, q in self._hits.items() if not q or now - q[-1] > self.window
        ]
        for ip in stale:
            del self._hits[ip]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.limit <= 0:
            await self.app(scope, receive, send)
            return

        now = time.monotonic()
        if now - self._last_sweep > self.window or len(self._hits) > self.max_tracked_ips:
            self._sweep(now)
            self._last_sweep = now

        ip = _client_ip(scope)
        q = self._hits[ip]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            await _send_error(
                send,
                429,
                "Rate limit exceeded. Try again shortly.",
                extra_headers=[(b"retry-after", b"60")],
            )
            return
        q.append(now)
        await self.app(scope, receive, send)


class BodySizeLimitMiddleware:
    """Reject requests whose body exceeds `max_bytes`, enforced on the actual stream so a
    chunked or length-omitted body can't bypass the Content-Length check."""

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

        # Buffer up to the cap, then replay to the app; `pending` carries any non-request
        # message (e.g. http.disconnect) read while buffering.
        chunks: list[bytes] = []
        total = 0
        pending: Message | None = None
        more = True
        while more:
            message = await receive()
            if message["type"] != "http.request":
                pending = message
                break
            total += len(message.get("body", b""))
            if total > self.max_bytes:
                await _send_error(send, 413, "Request body too large.")
                return
            chunks.append(message.get("body", b""))
            more = message.get("more_body", False)

        replayed = False

        async def replay_receive() -> Message:
            nonlocal replayed, pending
            if not replayed:
                replayed = True
                return {
                    "type": "http.request",
                    "body": b"".join(chunks),
                    "more_body": False,
                }
            if pending is not None:
                msg, pending = pending, None
                return msg
            return await receive()

        await self.app(scope, replay_receive, send)


class OriginValidationMiddleware:
    """Validate the Origin header against an allowlist. Empty allowlist = allow any (public);
    requests with no Origin (non-browser clients) always pass."""

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
        if origin is None or origin in self.allowed:
            await self.app(scope, receive, send)
            return
        await _send_error(send, 403, "Origin not allowed.")


class HostValidationMiddleware:
    """Validate the Host header against an allowlist (DNS-rebinding defense). Empty allowlist
    = allow any (public). A trailing `:*` in an entry allows any port."""

    def __init__(self, app: ASGIApp, allowed_hosts: list[str] | None = None) -> None:
        self.app = app
        self.allowed = {h.strip() for h in (allowed_hosts or []) if h.strip()}

    def _ok(self, host: str) -> bool:
        if host in self.allowed:
            return True
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
