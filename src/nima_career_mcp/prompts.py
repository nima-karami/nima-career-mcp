"""MCP prompt templates (opt-in, stubbed).

Prompts are user-controlled slash-command templates. Client support is uneven (notably,
some clients mishandle prompt parameters), so these are left unwired by default. The tool
surface already covers every use case. Uncomment `register_prompts` wiring in server.py and
the bodies below to enable them once you've verified your target clients support prompts.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .service import CareerService


def register_prompts(mcp: FastMCP, service: CareerService) -> None:
    @mcp.prompt()
    def tailored_resume(focus: str) -> str:
        """Slash-command: draft a resume for a given focus using only approved data."""
        return (
            f"Call assemble_resume with focus={focus!r}, then present the returned draft. "
            "Do not add any facts beyond what the tool returns."
        )

    @mcp.prompt()
    def interview_nima(topic: str) -> str:
        """Slash-command: dig into a topic from Nima's background."""
        return (
            f"Use search_experience and get_role to gather evidence about {topic!r}, "
            "then answer grounded strictly in that evidence."
        )
