"""Shim so `uv run mcp dev dev_server.py` works with this src-layout package.

`mcp dev` imports its target file BY PATH, which gives that file no parent package — so a
module using relative imports (like src/nima_career_mcp/server.py, with `from .corpus ...`)
fails with "attempted relative import with no known parent package". This shim is safe to
import by path: it pulls in the real server via an ABSOLUTE import, which loads it as part
of the installed `nima_career_mcp` package so its relative imports resolve normally.

In normal use prefer the entry point spawned by the Inspector:
    npx -y @modelcontextprotocol/inspector uv run nima-career-mcp
"""

from nima_career_mcp.server import mcp

__all__ = ["mcp"]
