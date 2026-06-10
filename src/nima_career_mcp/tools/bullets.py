"""Pre-approved resume bullets tool."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..service import BulletList, CareerService


def register_bullets(mcp: FastMCP, service: CareerService) -> None:
    @mcp.tool()
    def list_bullets(
        role_id: str | None = None,
        project_id: str | None = None,
        tags: list[str] | None = None,
        limit: int | None = None,
    ) -> BulletList:
        """List curated, hiring-manager-safe resume bullets.

        Each bullet is pre-approved and cites the evidence ids it derives from. Filter by
        role_id, project_id, and/or tags (AND). With no filters, returns all bullets.
        """
        return service.list_bullets(role_id=role_id, project_id=project_id, tags=tags, limit=limit)
