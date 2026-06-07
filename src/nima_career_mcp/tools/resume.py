"""The headline feature: assemble a tailored resume draft from approved material only."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..service import CareerService, ResumeDraft


def register_resume(mcp: FastMCP, service: CareerService) -> None:
    @mcp.tool()
    def assemble_resume(
        focus: str | None = None,
        role_ids: list[str] | None = None,
        project_ids: list[str] | None = None,
        skill_categories: list[str] | None = None,
        length: str = "full",
        format: str = "structured",
    ) -> ResumeDraft:
        """Assemble a tailored resume draft for a query (e.g. "backend-leaning").

        SELECTS and ORDERS the most relevant approved roles, evidence, bullets, and skills
        for `focus` (or for the explicit `role_ids`/`project_ids`), and fills an approved
        summary template — it never authors new facts, employers, dates, or metrics.

        Args:
            focus: free-text angle, e.g. "0-to-1 product" or "backend".
            role_ids / project_ids: pin specific items instead of ranking by focus.
            skill_categories: restrict the skills section.
            length: "full" or "onepage" (caps roles/bullets).
            format: "structured" (default) or "markdown" (also returns rendered markdown).

        The returned draft includes a `provenance` list of corpus ids and a `disclaimer`.
        A consuming agent may rephrase for fit but MUST NOT add claims not present here.
        """
        return service.assemble_resume(
            focus=focus,
            role_ids=role_ids,
            project_ids=project_ids,
            skill_categories=skill_categories,
            length=length,
            format=format,
        )
