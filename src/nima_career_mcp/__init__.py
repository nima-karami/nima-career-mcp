"""nima-career-mcp: a public, read-only MCP server over a vetted career corpus."""

from __future__ import annotations

__version__ = "0.1.0"


def main() -> None:
    # Imported lazily so `import nima_career_mcp` doesn't load the corpus/build the app.
    from .server import main as _main

    _main()


__all__ = ["main", "__version__"]
