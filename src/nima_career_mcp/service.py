"""CareerService — all read/query/assemble logic, independent of MCP wiring.

Tools (mcp layer) are thin wrappers around these methods, and tests call these methods
directly. Every method returns a Pydantic response model, so the MCP layer emits
`structuredContent` for free.

Honesty guarantee: every field of every response is sourced from the corpus. `assemble_resume`
SELECTS and ORDERS approved evidence/bullets and fills approved summary templates — it never
authors new facts, employers, dates, or metrics.
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, Field

from .corpus import Bullet, Corpus, Profile, Project, Role, SkillCategory
from .grouping import (
    ExperienceList,
    fmt_range,
    group_into_tenures,
    month_index,
    split_into_stints,
)
from .search import SearchHit, search

# --- response models -------------------------------------------------------------


class RoleSummary(BaseModel):
    id: str
    org: str
    company_id: str | None
    title: str
    start: str
    end: str | None
    location: str | None
    summary: str
    tags: list[str]


class RoleList(BaseModel):
    roles: list[RoleSummary]


class ProjectSummary(BaseModel):
    id: str
    name: str
    role_id: str | None
    blurb: str
    tags: list[str]


class ProjectList(BaseModel):
    projects: list[ProjectSummary]


class SkillList(BaseModel):
    categories: list[SkillCategory]


class BulletList(BaseModel):
    bullets: list[Bullet]


class SearchResultItem(BaseModel):
    id: str
    kind: str
    title: str
    snippet: str
    score: float
    source_ids: list[str]
    tags: list[str]


class SearchResults(BaseModel):
    query: str
    hits: list[SearchResultItem]


class ResumeRole(BaseModel):
    role_id: str
    org: str
    company_id: str
    title: str
    dates: str
    start: str
    end: str | None
    location: str | None
    bullets: list[str]
    bullet_ids: list[str]


class ResumeProject(BaseModel):
    project_id: str
    name: str
    bullets: list[str]


class ResumeDraft(BaseModel):
    """A tailored resume draft assembled entirely from approved corpus material."""

    focus: str | None
    header: dict[str, str]
    summary: str
    roles: list[ResumeRole]
    projects: list[ResumeProject]
    skills: list[SkillCategory]
    provenance: list[str] = Field(
        description="Corpus ids (evidence/bullet/role) every line traces back to."
    )
    disclaimer: str
    markdown: str | None = None


_DISCLAIMER = (
    "All content is drawn verbatim from Nima Karami's vetted, public-safe career corpus. "
    "No facts, employers, dates, or metrics were generated. Rephrase for fit if you like, "
    "but do not add claims that are not present above."
)


def _fmt_dates(role: Role) -> str:
    return f"{role.start} – {role.end or 'Present'}"


def _resume_stints(roles: list[ResumeRole]) -> list[list[ResumeRole]]:
    """Group selected resume rows by company_id and split into stints, newest first."""
    groups: dict[str, list[ResumeRole]] = {}
    order: list[str] = []
    for r in roles:
        if r.company_id not in groups:
            groups[r.company_id] = []
            order.append(r.company_id)
        groups[r.company_id].append(r)

    stints: list[list[ResumeRole]] = []
    for cid in order:
        stints.extend(split_into_stints(groups[cid], lambda x: x.start, lambda x: x.end))

    stints.sort(key=lambda s: max(month_index(p.start) for p in s), reverse=True)
    return stints


class CareerService:
    def __init__(self, corpus: Corpus) -> None:
        self.corpus = corpus

    # --- browse / query ----------------------------------------------------------

    def get_profile(self) -> Profile:
        return self.corpus.profile

    def list_roles(self) -> RoleList:
        return RoleList(
            roles=[
                RoleSummary(
                    id=r.id,
                    org=r.org,
                    company_id=r.company_id,
                    title=r.title,
                    start=r.start,
                    end=r.end,
                    location=r.location,
                    summary=r.summary,
                    tags=r.tags,
                )
                for r in self.corpus.roles
            ]
        )

    def list_experience(self) -> ExperienceList:
        """Roles grouped into company tenures (title progressions; gaps split into stints)."""
        return ExperienceList(companies=group_into_tenures(self.corpus.roles))

    def get_role(self, role_id: str) -> Role:
        role = self.corpus.role(role_id)
        if role is None:
            raise KeyError(f"No role with id '{role_id}'. Use list_roles to see valid ids.")
        return role

    def list_projects(
        self, tags: list[str] | None = None, role_id: str | None = None
    ) -> ProjectList:
        out: list[ProjectSummary] = []
        wanted = {t.lower() for t in (tags or [])}
        for p in self.corpus.projects:
            if role_id and p.role_id != role_id:
                continue
            if wanted and not wanted.issubset({t.lower() for t in p.tags}):
                continue
            out.append(
                ProjectSummary(id=p.id, name=p.name, role_id=p.role_id, blurb=p.blurb, tags=p.tags)
            )
        return ProjectList(projects=out)

    def get_project(self, project_id: str) -> Project:
        proj = self.corpus.project(project_id)
        if proj is None:
            raise KeyError(
                f"No project with id '{project_id}'. Use list_projects to see valid ids."
            )
        return proj

    def list_skills(self, category: str | None = None) -> SkillList:
        cats = self.corpus.skills
        if category:
            cats = [c for c in cats if c.category.lower() == category.lower()]
        return SkillList(categories=cats)

    def search_experience(
        self,
        query: str,
        kinds: list[str] | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> SearchResults:
        hits: list[SearchHit] = search(self.corpus, query, kinds, tags, limit)
        return SearchResults(
            query=query,
            hits=[
                SearchResultItem(
                    id=h.id,
                    kind=h.kind,
                    title=h.title,
                    snippet=h.snippet,
                    score=h.score,
                    source_ids=h.source_ids,
                    tags=h.tags,
                )
                for h in hits
            ],
        )

    def list_bullets(
        self,
        role_id: str | None = None,
        project_id: str | None = None,
        tags: list[str] | None = None,
        limit: int | None = None,
    ) -> BulletList:
        bullets: list[Bullet]
        if role_id:
            bullets = self.get_role(role_id).bullets
        elif project_id:
            bullets = self.get_project(project_id).bullets
        else:
            bullets = self.corpus.all_bullets()

        wanted = {t.lower() for t in (tags or [])}
        if wanted:
            bullets = [b for b in bullets if wanted.issubset({t.lower() for t in b.tags})]
        if limit is not None:
            bullets = bullets[:limit]
        return BulletList(bullets=bullets)

    # --- tailored assembly -------------------------------------------------------

    def assemble_resume(
        self,
        focus: str | None = None,
        role_ids: list[str] | None = None,
        project_ids: list[str] | None = None,
        skill_categories: list[str] | None = None,
        length: str = "full",
        format: str = "structured",
    ) -> ResumeDraft:
        """Assemble a tailored resume draft from approved material only.

        Selection logic:
          * roles: explicit `role_ids`, else `focus`-ranked, else all (recency order).
          * bullets within each role: `focus`-ranked subset, else all.
          * `length="onepage"` caps roles/bullets; `length="full"` keeps everything selected.
          * summary: an approved `summary_templates` line filled with corpus-derived values.
        Every emitted line is corpus text; `provenance` lists the ids it traces back to.
        """
        corpus = self.corpus
        provenance: list[str] = []

        # 1) Select roles.
        roles: list[Role]
        if role_ids:
            roles = [r for rid in role_ids if (r := corpus.role(rid)) is not None]
        elif focus:
            ranked = search(corpus, focus, kinds=["role"], limit=len(corpus.roles))
            roles = []
            for h in ranked:
                if h.score <= 0:
                    continue
                r = corpus.role(h.id)
                if r is not None:
                    roles.append(r)
        else:
            roles = list(corpus.roles)

        max_roles = 4 if length == "onepage" else len(roles)
        roles = roles[:max_roles]

        max_bullets = 3 if length == "onepage" else 99

        resume_roles: list[ResumeRole] = []
        for r in roles:
            bullets = self._select_bullets(r.bullets, focus, max_bullets)
            for b in bullets:
                provenance.extend(b.source_ids or [b.id])
            provenance.append(r.id)
            resume_roles.append(
                ResumeRole(
                    role_id=r.id,
                    org=r.org,
                    company_id=r.company_id or r.id,
                    title=r.title,
                    dates=_fmt_dates(r),
                    start=r.start,
                    end=r.end,
                    location=r.location,
                    bullets=[b.text for b in bullets],
                    bullet_ids=[b.id for b in bullets],
                )
            )

        # 2) Select projects (explicit ids, or those tied to the chosen roles when focused).
        resume_projects: list[ResumeProject] = []
        chosen_project_ids = set(project_ids or [])
        if not chosen_project_ids and focus:
            ranked_p = search(corpus, focus, kinds=["project"], limit=3)
            chosen_project_ids = {h.id for h in ranked_p if h.score > 0}
        for pid in chosen_project_ids:
            proj = corpus.project(pid)
            if proj is None:
                continue
            pbullets = self._select_bullets(proj.bullets, focus, max_bullets)
            for b in pbullets:
                provenance.extend(b.source_ids or [b.id])
            provenance.append(proj.id)
            resume_projects.append(
                ResumeProject(
                    project_id=proj.id,
                    name=proj.name,
                    bullets=[b.text for b in pbullets],
                )
            )

        # 3) Skills.
        skills = corpus.skills
        if skill_categories:
            wanted = {c.lower() for c in skill_categories}
            skills = [c for c in skills if c.category.lower() in wanted]

        # 4) Summary — fill an approved template with corpus-derived values only.
        summary = self._build_summary(roles)

        header = {
            "name": corpus.profile.name,
            "headline": corpus.profile.headline,
            "location": corpus.profile.location or "",
            **corpus.profile.links,
        }

        draft = ResumeDraft(
            focus=focus,
            header={k: v for k, v in header.items() if v},
            summary=summary,
            roles=resume_roles,
            projects=resume_projects,
            skills=skills,
            provenance=sorted(set(provenance)),
            disclaimer=_DISCLAIMER,
        )
        if format == "markdown":
            draft.markdown = self._render_markdown(draft)
        return draft

    # --- helpers -----------------------------------------------------------------

    @staticmethod
    def _select_bullets(bullets: list[Bullet], focus: str | None, limit: int) -> list[Bullet]:
        if not bullets:
            return []
        if not focus:
            return bullets[:limit]
        from .search import _score  # local import to keep the scoring rule in one place

        ranked = sorted(bullets, key=lambda b: _score(focus, b.text, b.tags), reverse=True)
        return ranked[:limit]

    def _build_summary(self, roles: list[Role]) -> str:
        templates = self.corpus.profile.summary_templates
        if not templates:
            return self.corpus.profile.headline
        tag_counts = Counter(t for r in roles for t in r.tags)
        top_tags = ", ".join(t for t, _ in tag_counts.most_common(3))
        template = templates[0]
        return template.format(
            headline=self.corpus.profile.headline,
            top_tags=top_tags or "product and engineering",
            name=self.corpus.profile.name,
        )

    @staticmethod
    def _render_markdown(draft: ResumeDraft) -> str:
        lines: list[str] = []
        lines.append(f"# {draft.header.get('name', '')}")
        if draft.header.get("headline"):
            lines.append(f"**{draft.header['headline']}**")
        if draft.header.get("location"):
            lines.append(draft.header["location"])
        lines.append("")
        if draft.summary:
            lines.append(draft.summary)
            lines.append("")
        if draft.roles:
            lines.append("## Experience")
            for stint in _resume_stints(draft.roles):
                positions = sorted(stint, key=lambda p: month_index(p.start), reverse=True)
                if len(positions) == 1:
                    p = positions[0]
                    lines.append(f"### {p.title} — {p.org}  ({p.dates})")
                    for b in p.bullets:
                        lines.append(f"- {b}")
                    lines.append("")
                else:
                    # Title progression at one company: a single company header with
                    # each position nested beneath it.
                    start = min((p.start for p in positions), key=month_index)
                    ends = [p.end for p in positions]
                    end = (
                        None
                        if any(e is None for e in ends)
                        else max((e for e in ends if e), key=month_index)
                    )
                    lines.append(f"### {positions[0].org}  ({fmt_range(start, end)})")
                    for p in positions:
                        lines.append(f"#### {p.title}  ({p.dates})")
                        for b in p.bullets:
                            lines.append(f"- {b}")
                    lines.append("")
        if draft.projects:
            lines.append("## Projects")
            for p in draft.projects:
                lines.append(f"### {p.name}")
                for b in p.bullets:
                    lines.append(f"- {b}")
                lines.append("")
        if draft.skills:
            lines.append("## Skills")
            for cat in draft.skills:
                names = ", ".join(s.name for s in cat.skills)
                lines.append(f"- **{cat.category}:** {names}")
            lines.append("")
        return "\n".join(lines).strip()
