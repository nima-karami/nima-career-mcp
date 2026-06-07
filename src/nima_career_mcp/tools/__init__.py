"""Tool registration. All tools are read-only and return structured content."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..service import CareerService
from .browse import register_browse
from .bullets import register_bullets
from .resume import register_resume


def register_all(mcp: FastMCP, service: CareerService) -> None:
    register_browse(mcp, service)
    register_bullets(mcp, service)
    register_resume(mcp, service)
