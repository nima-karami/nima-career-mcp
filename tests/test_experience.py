"""Grouping roles into company tenures: title progression and leave/return stints."""

from __future__ import annotations

from nima_career_mcp.corpus import Corpus, Profile, Role
from nima_career_mcp.grouping import group_into_tenures
from nima_career_mcp.service import CareerService


def test_progression_groups_into_one_tenure(service: CareerService) -> None:
    exp = service.list_experience()
    timeplay = next(c for c in exp.companies if c.company_id == "timeplay")
    # All three titles collapse into a single continuous tenure...
    assert len(timeplay.positions) == 3
    # ...ordered newest-first, and still "Present" because the lead role is open-ended.
    assert timeplay.positions[0].title == "Lead Fullstack Developer"
    assert timeplay.end is None
    assert timeplay.start == "2021-03"


def _role(rid: str, title: str, start: str, end: str | None) -> Role:
    return Role(id=rid, company_id="acme", org="Acme", title=title, start=start, end=end)


def test_leave_and_return_splits_into_two_tenures() -> None:
    # Same company_id, but a two-year gap between the two stints.
    corpus = Corpus(
        profile=Profile(name="Test"),
        roles=[
            _role("acme-1", "Engineer", "2016-01", "2018-01"),
            _role("acme-2", "Senior Engineer", "2020-01", "2022-01"),
        ],
    )
    tenures = group_into_tenures(corpus.roles)
    acme = [t for t in tenures if t.company_id == "acme"]
    assert len(acme) == 2  # the gap splits the company into two separate tenures
    # Newest tenure first.
    assert acme[0].start == "2020-01"
    assert acme[1].start == "2016-01"


def test_promotion_without_gap_stays_one_tenure() -> None:
    corpus = Corpus(
        profile=Profile(name="Test"),
        roles=[
            _role("acme-1", "Engineer", "2020-01", "2021-06"),
            _role("acme-2", "Senior Engineer", "2021-06", None),
        ],
    )
    tenures = group_into_tenures(corpus.roles)
    assert len(tenures) == 1
    assert len(tenures[0].positions) == 2
    assert tenures[0].end is None


def test_resume_markdown_groups_company_positions(service: CareerService) -> None:
    draft = service.assemble_resume(format="markdown")
    md = draft.markdown or ""
    # One company header for TimePlay, with each title nested beneath it.
    assert md.count("### TimePlay") == 1
    for title in ("Lead Fullstack Developer", "Fullstack Developer", "Frontend Developer"):
        assert title in md
