"""Pydantic models + loader + integrity validation for the public-safe career corpus.

This module is the single chokepoint that makes the project's core guarantee enforceable
in code: *the server can only ever return data that exists in the corpus*. Every tool reads
through these validated models, and `Corpus.validate_integrity()` fails loudly if a bullet
or skill cites evidence that does not exist.

The corpus is curated YAML under `corpus/` (see CORPUS.md). It contains NO secrets and NO
private application-tracking data — that lives in a separate private repo.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError


class CorpusError(RuntimeError):
    """Raised when the corpus is missing, malformed, or fails integrity checks."""


class Metric(BaseModel):
    """A single approved, quantified claim. Only metrics you vet appear here."""

    label: str
    value: str


class Evidence(BaseModel):
    """A granular, factual statement about something done in a role or project.

    This is the 'base list of evidence' the resume tool draws from.
    """

    id: str
    text: str
    metrics: list[Metric] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class Bullet(BaseModel):
    """A curated, resume-ready phrasing derived from one or more `Evidence` items."""

    id: str
    text: str
    metrics: list[Metric] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class Link(BaseModel):
    label: str
    url: str


class Role(BaseModel):
    """A single job/title. `end=None` means 'present'.

    Multiple roles can share a `company_id` to express a title progression within one
    company (e.g. Frontend -> Fullstack -> Lead). Grouping into company tenures happens at
    render time (see grouping.py); the data stays flat so a client can group or not.
    """

    id: str
    org: str
    title: str
    start: str  # "YYYY-MM"
    end: str | None = None  # "YYYY-MM" or null for present
    company_id: str | None = None  # shared key for roles at the same company
    location: str | None = None
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    bullets: list[Bullet] = Field(default_factory=list)


class Project(BaseModel):
    id: str
    name: str
    role_id: str | None = None
    blurb: str = ""
    tags: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    bullets: list[Bullet] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)


class Skill(BaseModel):
    name: str
    proficiency: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class SkillCategory(BaseModel):
    category: str
    skills: list[Skill] = Field(default_factory=list)


class Profile(BaseModel):
    name: str
    headline: str = ""
    location: str | None = None
    links: dict[str, str] = Field(default_factory=dict)
    bio: str = ""
    # Approved skeleton lines used to assemble a summary. {headline} and {top_tags} are
    # filled from corpus values only — no free-form sentence generation at runtime.
    summary_templates: list[str] = Field(default_factory=list)
    contact_policy: str = ""


class Corpus(BaseModel):
    profile: Profile
    roles: list[Role] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    skills: list[SkillCategory] = Field(default_factory=list)

    # --- lookups -----------------------------------------------------------------

    def role(self, role_id: str) -> Role | None:
        return next((r for r in self.roles if r.id == role_id), None)

    def project(self, project_id: str) -> Project | None:
        return next((p for p in self.projects if p.id == project_id), None)

    def all_evidence_ids(self) -> set[str]:
        ids: set[str] = set()
        for r in self.roles:
            ids.update(e.id for e in r.evidence)
        for p in self.projects:
            ids.update(e.id for e in p.evidence)
        return ids

    def all_bullets(self) -> list[Bullet]:
        out: list[Bullet] = []
        for r in self.roles:
            out.extend(r.bullets)
        for p in self.projects:
            out.extend(p.bullets)
        return out

    # --- integrity ---------------------------------------------------------------

    def validate_integrity(self) -> None:
        """Fail if any referential or uniqueness invariant is violated.

        Guarantees that every claim is traceable to vetted evidence, which is what makes
        'the model can only return what's in the corpus' true by construction.
        """
        problems: list[str] = []
        evidence_ids = self.all_evidence_ids()

        # Unique ids across roles, projects, evidence, bullets.
        self._check_unique([r.id for r in self.roles], "role", problems)
        self._check_unique([p.id for p in self.projects], "project", problems)
        bullet_ids = [b.id for b in self.all_bullets()]
        self._check_unique(bullet_ids, "bullet", problems)
        self._check_unique(list(self._evidence_id_list()), "evidence", problems)

        # Every bullet's source_ids must resolve to real evidence.
        for b in self.all_bullets():
            for sid in b.source_ids:
                if sid not in evidence_ids:
                    problems.append(f"bullet '{b.id}' cites missing evidence id '{sid}'")

        # Every skill's evidence_ids must resolve.
        for cat in self.skills:
            for s in cat.skills:
                for sid in s.evidence_ids:
                    if sid not in evidence_ids:
                        problems.append(f"skill '{s.name}' cites missing evidence id '{sid}'")

        # Projects that name a role must point at a real role.
        role_ids = {r.id for r in self.roles}
        for p in self.projects:
            if p.role_id and p.role_id not in role_ids:
                problems.append(f"project '{p.id}' references missing role_id '{p.role_id}'")

        # Roles sharing a company_id must agree on the display org name.
        org_by_company: dict[str, str] = {}
        for r in self.roles:
            if not r.company_id:
                continue
            existing = org_by_company.setdefault(r.company_id, r.org)
            if existing != r.org:
                problems.append(
                    f"role '{r.id}' org '{r.org}' conflicts with '{existing}' "
                    f"for company_id '{r.company_id}'"
                )

        if problems:
            raise CorpusError("Corpus integrity check failed:\n  - " + "\n  - ".join(problems))

    def _evidence_id_list(self) -> list[str]:
        out: list[str] = []
        for r in self.roles:
            out.extend(e.id for e in r.evidence)
        for p in self.projects:
            out.extend(e.id for e in p.evidence)
        return out

    @staticmethod
    def _check_unique(ids: list[str], kind: str, problems: list[str]) -> None:
        seen: set[str] = set()
        for i in ids:
            if i in seen:
                problems.append(f"duplicate {kind} id '{i}'")
            seen.add(i)


# --- loading ---------------------------------------------------------------------


def default_corpus_dir() -> Path:
    """Resolve the corpus directory.

    Honors the NIMA_CORPUS_DIR env var (used in Docker/Fly); otherwise falls back to the
    `corpus/` folder at the repo root relative to this file (used in local dev).
    """
    env = os.environ.get("NIMA_CORPUS_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "corpus"


def _read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_corpus(corpus_dir: Path | None = None) -> Corpus:
    """Load, validate, and integrity-check the corpus from disk.

    Layout (see CORPUS.md):
        corpus/profile.yaml
        corpus/roles/*.yaml
        corpus/projects/*.yaml
        corpus/skills.yaml
    """
    root = corpus_dir or default_corpus_dir()
    if not root.exists():
        raise CorpusError(f"Corpus directory not found: {root}")

    profile_path = root / "profile.yaml"
    if not profile_path.exists():
        raise CorpusError(f"Missing required file: {profile_path}")

    try:
        profile = Profile.model_validate(_read_yaml(profile_path))

        roles = [
            Role.model_validate(_read_yaml(p)) for p in sorted((root / "roles").glob("*.yaml"))
        ]
        projects = [
            Project.model_validate(_read_yaml(p))
            for p in sorted((root / "projects").glob("*.yaml"))
        ]

        skills_path = root / "skills.yaml"
        raw_skills = _read_yaml(skills_path) if skills_path.exists() else []
        skills = [SkillCategory.model_validate(c) for c in (raw_skills or [])]
    except ValidationError as exc:
        raise CorpusError(f"Corpus failed schema validation:\n{exc}") from exc

    corpus = Corpus(profile=profile, roles=roles, projects=projects, skills=skills)
    corpus.validate_integrity()
    return corpus
