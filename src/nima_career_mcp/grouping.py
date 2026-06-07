"""Render-time grouping of roles into company tenures (stints).

A `Role` is a single (company, title, date-range) record. Multiple roles can share a
`company_id` — a title progression within one company. This module groups those roles for
display, splitting a company into separate **tenures** when there is a date gap between
roles (so "left and came back two years later" renders as two blocks, while a promotion
sequence renders as one). Grouping is purely a presentation concern: the underlying data
stays flat so a client can group, split, or not group at all.
"""

from __future__ import annotations

from typing import Callable, TypeVar

from pydantic import BaseModel

from .corpus import Bullet, Role

T = TypeVar("T")


def month_index(ym: str) -> int:
    """Map "YYYY-MM" (or "YYYY") to a comparable integer month count."""
    parts = ym.split("-")
    year = int(parts[0])
    month = int(parts[1]) if len(parts) > 1 else 1
    return year * 12 + month


def fmt_range(start: str, end: str | None) -> str:
    return f"{start} – {end or 'Present'}"


def company_key(role: Role) -> str:
    """Stable grouping key: explicit company_id, else the role's own id (standalone)."""
    return role.company_id or role.id


def split_into_stints(
    items: list[T],
    get_start: Callable[[T], str],
    get_end: Callable[[T], str | None],
) -> list[list[T]]:
    """Sort items by start date and split into contiguous stints.

    A new stint begins when the gap between one item's end and the next item's start is
    more than one month. An open-ended item (end=None) never starts a gap.
    """
    if not items:
        return []
    ordered = sorted(items, key=lambda x: month_index(get_start(x)))
    stints: list[list[T]] = [[ordered[0]]]
    for prev, nxt in zip(ordered, ordered[1:]):
        prev_end = get_end(prev)
        if prev_end is None or month_index(get_start(nxt)) - month_index(prev_end) <= 1:
            stints[-1].append(nxt)
        else:
            stints.append([nxt])
    return stints


# --- grouped browse models (used by list_experience) -----------------------------


class ExperiencePosition(BaseModel):
    role_id: str
    title: str
    start: str
    end: str | None
    dates: str
    location: str | None
    summary: str
    tags: list[str]
    bullets: list[Bullet]


class ExperienceTenure(BaseModel):
    company_id: str
    org: str
    location: str | None
    start: str
    end: str | None
    dates: str
    positions: list[ExperiencePosition]  # newest first


class ExperienceList(BaseModel):
    companies: list[ExperienceTenure]  # most recent tenure first


def _tenure_end(stint: list[Role]) -> str | None:
    ends = [r.end for r in stint]
    if any(e is None for e in ends):
        return None  # still ongoing
    return max((e for e in ends if e is not None), key=month_index)


def _build_tenure(company_id: str, stint: list[Role]) -> ExperienceTenure:
    start = min((r.start for r in stint), key=month_index)
    end = _tenure_end(stint)
    org = stint[0].org
    location = next((r.location for r in stint if r.location), None)
    positions = sorted(stint, key=lambda r: month_index(r.start), reverse=True)
    return ExperienceTenure(
        company_id=company_id,
        org=org,
        location=location,
        start=start,
        end=end,
        dates=fmt_range(start, end),
        positions=[
            ExperiencePosition(
                role_id=r.id,
                title=r.title,
                start=r.start,
                end=r.end,
                dates=fmt_range(r.start, r.end),
                location=r.location,
                summary=r.summary,
                tags=r.tags,
                bullets=r.bullets,
            )
            for r in positions
        ],
    )


def group_into_tenures(roles: list[Role]) -> list[ExperienceTenure]:
    """Group roles by company, split each company into stints, newest tenure first."""
    by_company: dict[str, list[Role]] = {}
    for r in roles:
        by_company.setdefault(company_key(r), []).append(r)

    tenures: list[ExperienceTenure] = []
    for cid, rs in by_company.items():
        for stint in split_into_stints(rs, lambda r: r.start, lambda r: r.end):
            tenures.append(_build_tenure(cid, stint))

    tenures.sort(key=lambda t: month_index(t.start), reverse=True)
    return tenures
