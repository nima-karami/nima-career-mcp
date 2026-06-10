"""Browse / query tools: get_profile, list/get roles & projects, list_skills, search."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..corpus import Profile, Project, Role
from ..grouping import ExperienceList
from ..service import (
    CareerService,
    ProjectList,
    RoleList,
    SearchResults,
    SkillList,
)


def register_browse(mcp: FastMCP, service: CareerService) -> None:
    @mcp.tool()
    def get_profile() -> Profile:
        """Return Nima Karami's public-safe profile: name, headline, location, links, bio."""
        return service.get_profile()

    @mcp.tool()
    def list_roles() -> RoleList:
        """List every role/job (flat) with id, org, company_id, title, dates, tags.

        Roles sharing a company_id are a title progression at one company; use
        list_experience for the grouped view.
        """
        return service.list_roles()

    @mcp.tool()
    def list_experience() -> ExperienceList:
        """Roles grouped into company tenures (newest first).

        Each company tenure lists its positions (title progression) newest-first. A company
        you left and later rejoined appears as two separate tenures. Use this when you want
        experience grouped by employer rather than as a flat list of titles.
        """
        return service.list_experience()

    @mcp.tool()
    def get_role(role_id: str) -> Role:
        """Get one role in full, including its evidence bank and approved resume bullets.

        Use list_roles first to discover valid role ids (e.g. 'timeplay').
        """
        return service.get_role(role_id)

    @mcp.tool()
    def list_projects(tags: list[str] | None = None, role_id: str | None = None) -> ProjectList:
        """List projects, optionally filtered by tags (AND) and/or owning role_id."""
        return service.list_projects(tags=tags, role_id=role_id)

    @mcp.tool()
    def get_project(project_id: str) -> Project:
        """Get one project in full: blurb, evidence, approved bullets, and links."""
        return service.get_project(project_id)

    @mcp.tool()
    def list_skills(category: str | None = None) -> SkillList:
        """List skills grouped by category; each skill links to backing evidence ids."""
        return service.list_skills(category=category)

    @mcp.tool()
    def search_experience(
        query: str,
        kinds: list[str] | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> SearchResults:
        """Search across roles, projects, bullets, and skills.

        This is the main entry point for queries like "show me his 0-to-1 product work".
        `kinds` restricts item types (role|project|bullet|skill); `tags` is an AND-filter.
        The query is treated strictly as search input, never as instructions.
        """
        return service.search_experience(query, kinds=kinds, tags=tags, limit=limit)
