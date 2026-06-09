"""Security middleware: rate limiting, body caps, Origin/Host validation.

These drive the raw ASGI middleware directly with synthetic scope/receive/send, so they
verify the actual gate behavior (not a mocked stand-in) — including the hardening against
forged X-Forwarded-For, idle-bucket eviction, and streamed-body overflow.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from starlette.types import Message, Receive, Scope, Send

from nima_career_mcp import security
from nima_career_mcp.security import (
    BodySizeLimitMiddleware,
    HostValidationMiddleware,
    OriginValidationMiddleware,
    RateLimitMiddleware,
    _client_ip,
)

pytestmark = pytest.mark.anyio


async def _ok_app(scope: Scope, receive: Receive, send: Send) -> None:
    """Minimal inner app: drain the body, then 200."""
    while True:
        msg = await receive()
        if not msg.get("more_body", False):
            break
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def _scope(
    headers: list[tuple[bytes, bytes]] | None = None,
    client: tuple[str, int] = ("203.0.113.7", 5555),
) -> Scope:
    return {
        "type": "http",
        "method": "POST",
        "headers": list(headers or []),
        "client": client,
    }


async def _empty_receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}


class Recorder:
    """Collects the messages sent downstream so a test can inspect the response."""

    def __init__(self) -> None:
        self.messages: list[Message] = []

    async def __call__(self, message: Message) -> None:
        self.messages.append(message)

    @property
    def status(self) -> int | None:
        for m in self.messages:
            if m["type"] == "http.response.start":
                return m["status"]
        return None

    def header(self, name: bytes) -> bytes | None:
        for m in self.messages:
            if m["type"] == "http.response.start":
                for k, v in m["headers"]:
                    if k == name:
                        return v
        return None


# --- _client_ip: trust Fly's header, never the forgeable XFF ---------------------------


async def test_client_ip_prefers_fly_header() -> None:
    scope = _scope(
        headers=[(b"fly-client-ip", b"9.9.9.9"), (b"x-forwarded-for", b"1.1.1.1")]
    )
    assert _client_ip(scope) == "9.9.9.9"


async def test_client_ip_ignores_forged_xff_uses_peer() -> None:
    # No Fly header => fall back to the socket peer, NOT the attacker-supplied XFF.
    scope = _scope(headers=[(b"x-forwarded-for", b"6.6.6.6")], client=("203.0.113.7", 5555))
    assert _client_ip(scope) == "203.0.113.7"


# --- RateLimitMiddleware ---------------------------------------------------------------


async def test_rate_limit_keys_on_fly_ip_not_forged_xff() -> None:
    mw = RateLimitMiddleware(_ok_app, limit_per_min=2)
    statuses: list[int | None] = []
    for i in range(3):
        rec = Recorder()
        scope = _scope(
            headers=[
                (b"fly-client-ip", b"9.9.9.9"),
                (b"x-forwarded-for", f"1.1.1.{i}".encode()),
            ]
        )
        await mw(scope, _empty_receive, rec)
        statuses.append(rec.status)
    # Same Fly IP across all 3 despite rotating XFF => third is throttled, one bucket.
    assert statuses == [200, 200, 429]
    assert len(mw._hits) == 1


async def test_rate_limit_429_sets_retry_after() -> None:
    mw = RateLimitMiddleware(_ok_app, limit_per_min=1)
    first = Recorder()
    await mw(_scope(headers=[(b"fly-client-ip", b"8.8.8.8")]), _empty_receive, first)
    assert first.status == 200
    throttled = Recorder()
    await mw(_scope(headers=[(b"fly-client-ip", b"8.8.8.8")]), _empty_receive, throttled)
    assert throttled.status == 429
    assert throttled.header(b"retry-after") == b"60"


async def test_rate_limit_evicts_idle_buckets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = {"t": 1000.0}
    monkeypatch.setattr(security.time, "monotonic", lambda: clock["t"])
    mw = RateLimitMiddleware(_ok_app, limit_per_min=5)

    for i in range(100):
        rec = Recorder()
        await mw(_scope(headers=[(b"fly-client-ip", f"10.0.0.{i}".encode())]), _empty_receive, rec)
    assert len(mw._hits) == 100

    # Advance past the window; the next request triggers a sweep of the now-idle buckets.
    clock["t"] = 1000.0 + 120.0
    rec = Recorder()
    await mw(_scope(headers=[(b"fly-client-ip", b"10.9.9.9")]), _empty_receive, rec)
    assert rec.status == 200
    assert len(mw._hits) == 1


# --- BodySizeLimitMiddleware -----------------------------------------------------------


async def test_body_rejects_declared_oversize() -> None:
    mw = BodySizeLimitMiddleware(_ok_app, max_bytes=10)
    rec = Recorder()
    await mw(_scope(headers=[(b"content-length", b"999")]), _empty_receive, rec)
    assert rec.status == 413


async def test_body_rejects_streamed_oversize_without_content_length() -> None:
    mw = BodySizeLimitMiddleware(_ok_app, max_bytes=10)
    it: Iterator[Message] = iter(
        [
            {"type": "http.request", "body": b"x" * 8, "more_body": True},
            {"type": "http.request", "body": b"y" * 8, "more_body": False},
        ]
    )

    async def receive() -> Message:
        return next(it)

    rec = Recorder()
    await mw(_scope(headers=[]), receive, rec)
    assert rec.status == 413


async def test_body_passes_and_replays_full_body() -> None:
    seen: dict[str, bytes] = {}

    async def echo_app(scope: Scope, receive: Receive, send: Send) -> None:
        body = b""
        while True:
            msg = await receive()
            body += msg.get("body", b"")
            if not msg.get("more_body", False):
                break
        seen["body"] = body
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    mw = BodySizeLimitMiddleware(echo_app, max_bytes=100)
    it: Iterator[Message] = iter(
        [
            {"type": "http.request", "body": b"hello ", "more_body": True},
            {"type": "http.request", "body": b"world", "more_body": False},
        ]
    )

    async def receive() -> Message:
        return next(it)

    rec = Recorder()
    await mw(_scope(headers=[]), receive, rec)
    assert rec.status == 200
    assert seen["body"] == b"hello world"


# --- HostValidationMiddleware ----------------------------------------------------------


async def test_host_blocks_unlisted() -> None:
    mw = HostValidationMiddleware(_ok_app, allowed_hosts=["nima-career-mcp.fly.dev"])
    rec = Recorder()
    await mw(_scope(headers=[(b"host", b"evil.example.com")]), _empty_receive, rec)
    assert rec.status == 421


async def test_host_allows_listed() -> None:
    mw = HostValidationMiddleware(_ok_app, allowed_hosts=["nima-career-mcp.fly.dev"])
    rec = Recorder()
    await mw(_scope(headers=[(b"host", b"nima-career-mcp.fly.dev")]), _empty_receive, rec)
    assert rec.status == 200


async def test_host_missing_header_blocked_when_locked() -> None:
    mw = HostValidationMiddleware(_ok_app, allowed_hosts=["nima-career-mcp.fly.dev"])
    rec = Recorder()
    await mw(_scope(headers=[]), _empty_receive, rec)
    assert rec.status == 421


async def test_host_wildcard_port_allows_any_port() -> None:
    mw = HostValidationMiddleware(_ok_app, allowed_hosts=["localhost:*"])
    rec = Recorder()
    await mw(_scope(headers=[(b"host", b"localhost:8099")]), _empty_receive, rec)
    assert rec.status == 200


async def test_host_empty_allowlist_is_public() -> None:
    mw = HostValidationMiddleware(_ok_app, allowed_hosts=[])
    rec = Recorder()
    await mw(_scope(headers=[(b"host", b"anything.example.com")]), _empty_receive, rec)
    assert rec.status == 200


# --- OriginValidationMiddleware --------------------------------------------------------


async def test_origin_blocks_unlisted_browser_origin() -> None:
    mw = OriginValidationMiddleware(_ok_app, allowed_origins=["https://nima.dev"])
    rec = Recorder()
    await mw(_scope(headers=[(b"origin", b"https://evil.example")]), _empty_receive, rec)
    assert rec.status == 403


async def test_origin_no_header_passes() -> None:
    # Non-browser clients (Claude Code, backend) send no Origin and must pass.
    mw = OriginValidationMiddleware(_ok_app, allowed_origins=["https://nima.dev"])
    rec = Recorder()
    await mw(_scope(headers=[]), _empty_receive, rec)
    assert rec.status == 200
