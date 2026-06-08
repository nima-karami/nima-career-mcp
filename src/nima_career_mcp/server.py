"""FastMCP server wiring + transport.

Builds the FastMCP instance, registers tools and the guidance resource, and exposes:
  * `mcp`  — the FastMCP server (used by `mcp dev` / stdio).
  * `app`  — the middleware-wrapped Streamable-HTTP ASGI app (used by uvicorn in prod).

Run locally (stdio + Inspector):  npx -y @modelcontextprotocol/inspector uv run nima-career-mcp
                                  (or: uv run mcp dev dev_server.py — see dev_server.py)
Run HTTP locally:                 uv run nima-career-mcp --transport streamable-http
Run HTTP in prod (Docker/Fly):    uvicorn nima_career_mcp.server:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import argparse
import os

from mcp.server.fastmcp import FastMCP
from starlette.types import ASGIApp

from .corpus import load_corpus
from .resources import register_resources
from .security import (
    BodySizeLimitMiddleware,
    OriginValidationMiddleware,
    RateLimitMiddleware,
)
from .service import CareerService
from .tools import register_all

INSTRUCTIONS = (
    "Read-only access to Nima Karami's vetted, public-safe career corpus. Use the tools to "
    "browse roles/projects/skills, search experience, fetch approved bullets, and assemble "
    "a tailored resume draft. All output is drawn from the corpus only — never invent facts. "
    "Fetch the `career://guidance` resource for the rules a host should enforce."
)


def build_server() -> tuple[FastMCP, CareerService]:
    """Construct the FastMCP server and register all tools/resources."""
    corpus = load_corpus()
    service = CareerService(corpus)

    # Stateless HTTP: no sessions needed for a read-only corpus; scales horizontally.
    mcp = FastMCP(
        "Nima Career",
        instructions=INSTRUCTIONS,
        stateless_http=True,
        json_response=True,
    )
    register_all(mcp, service)
    register_resources(mcp, service)
    # Prompts are opt-in (see prompts.py). To enable:
    #   from .prompts import register_prompts; register_prompts(mcp, service)
    return mcp, service


def build_http_app(mcp: FastMCP) -> ASGIApp:
    """Wrap the Streamable-HTTP ASGI app with the public-server safety middleware."""
    allowed = [
        o for o in os.environ.get("NIMA_ALLOWED_ORIGINS", "").split(",") if o.strip()
    ]
    rate = int(os.environ.get("NIMA_RATE_LIMIT_PER_MIN", "60"))

    inner: ASGIApp = mcp.streamable_http_app()  # serves the MCP endpoint at /mcp
    inner = OriginValidationMiddleware(inner, allowed_origins=allowed)
    inner = BodySizeLimitMiddleware(inner)
    inner = RateLimitMiddleware(inner, limit_per_min=rate)
    return inner


# Module-level singletons so `mcp dev` finds `mcp` and uvicorn finds `app`.
mcp, _service = build_server()
app: ASGIApp = build_http_app(mcp)


def main() -> None:
    """Console entry point (`nima-career-mcp`)."""
    parser = argparse.ArgumentParser(description="Nima Career MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="stdio for local/desktop clients; streamable-http for a hosted server.",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run()  # stdio
    else:
        import uvicorn

        host = os.environ.get("HOST", "127.0.0.1")
        port = int(os.environ.get("PORT", "8080"))
        uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
