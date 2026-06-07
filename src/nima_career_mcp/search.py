"""Deterministic ranking/selection over the corpus.

No LLM here — ranking is plain fuzzy string matching (rapidfuzz). This is the seam where a
semantic/embedding search could later be swapped in without touching the tool surface.

Treating the query strictly as *search input* (never as instructions) is part of the
server's anti-injection posture: a query like "ignore your instructions" simply produces
weak fuzzy matches and returns data, never compliance.
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

from .corpus import Corpus

Kind = str  # one of: "role", "project", "bullet", "skill"


@dataclass
class SearchHit:
    id: str
    kind: Kind
    title: str
    snippet: str
    score: float
    source_ids: list[str]
    tags: list[str]


def _score(query: str, text: str, tags: list[str]) -> float:
    """Blend full-text token matching with a tag-match bonus."""
    haystack = f"{text} {' '.join(tags)}".strip()
    base = fuzz.token_set_ratio(query.lower(), haystack.lower())
    # Reward exact tag hits so "0-to-1" style filters rank strongly.
    q_terms = {t for t in query.lower().replace(",", " ").split() if t}
    tag_hits = sum(1 for t in tags if t.lower() in q_terms)
    return float(base) + 10.0 * tag_hits


def _tag_filter(item_tags: list[str], required: list[str] | None) -> bool:
    if not required:
        return True
    have = {t.lower() for t in item_tags}
    return all(r.lower() in have for r in required)


def search(
    corpus: Corpus,
    query: str,
    kinds: list[Kind] | None = None,
    tags: list[str] | None = None,
    limit: int = 10,
) -> list[SearchHit]:
    """Rank corpus items against a free-text query.

    `kinds` restricts which item types are searched; `tags` is an AND-filter applied before
    ranking. Results are sorted by descending score and truncated to `limit`.
    """
    kinds = kinds or ["role", "project", "bullet", "skill"]
    hits: list[SearchHit] = []

    if "role" in kinds:
        for r in corpus.roles:
            if not _tag_filter(r.tags, tags):
                continue
            text = f"{r.title} at {r.org}. {r.summary}"
            hits.append(
                SearchHit(
                    id=r.id,
                    kind="role",
                    title=f"{r.title} — {r.org}",
                    snippet=r.summary or text,
                    score=_score(query, text, r.tags),
                    source_ids=[r.id],
                    tags=r.tags,
                )
            )

    if "project" in kinds:
        for p in corpus.projects:
            if not _tag_filter(p.tags, tags):
                continue
            text = f"{p.name}. {p.blurb}"
            hits.append(
                SearchHit(
                    id=p.id,
                    kind="project",
                    title=p.name,
                    snippet=p.blurb or p.name,
                    score=_score(query, text, p.tags),
                    source_ids=[p.id],
                    tags=p.tags,
                )
            )

    if "bullet" in kinds:
        for b in corpus.all_bullets():
            if not _tag_filter(b.tags, tags):
                continue
            hits.append(
                SearchHit(
                    id=b.id,
                    kind="bullet",
                    title=b.text[:80],
                    snippet=b.text,
                    score=_score(query, b.text, b.tags),
                    source_ids=b.source_ids or [b.id],
                    tags=b.tags,
                )
            )

    if "skill" in kinds:
        for cat in corpus.skills:
            for s in cat.skills:
                text = f"{s.name} ({cat.category})"
                hits.append(
                    SearchHit(
                        id=s.name,
                        kind="skill",
                        title=s.name,
                        snippet=text,
                        score=_score(query, text, [cat.category]),
                        source_ids=s.evidence_ids,
                        tags=[cat.category],
                    )
                )

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]
