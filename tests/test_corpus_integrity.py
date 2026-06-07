"""The corpus must load, schema-validate, and pass referential integrity."""

from __future__ import annotations

import pytest

from nima_career_mcp.corpus import (
    Bullet,
    Corpus,
    CorpusError,
    Evidence,
    Profile,
    Role,
)


def test_shipped_corpus_loads_and_is_valid(corpus: Corpus) -> None:
    assert corpus.profile.name
    assert corpus.roles, "expected at least the seed role"
    assert corpus.role("timeplay") is not None


def test_every_bullet_source_resolves(corpus: Corpus) -> None:
    evidence_ids = corpus.all_evidence_ids()
    for b in corpus.all_bullets():
        for sid in b.source_ids:
            assert sid in evidence_ids, f"{b.id} -> {sid}"


def test_integrity_rejects_dangling_bullet_source() -> None:
    broken = Corpus(
        profile=Profile(name="Test"),
        roles=[
            Role(
                id="r1",
                org="Org",
                title="Eng",
                start="2020-01",
                evidence=[Evidence(id="e1", text="did a thing")],
                # cites e-missing, which does not exist:
                bullets=[Bullet(id="b1", text="claim", source_ids=["e-missing"])],
            )
        ],
    )
    with pytest.raises(CorpusError):
        broken.validate_integrity()


def test_integrity_rejects_duplicate_ids() -> None:
    dup = Corpus(
        profile=Profile(name="Test"),
        roles=[
            Role(id="dup", org="A", title="T", start="2020-01"),
            Role(id="dup", org="B", title="T", start="2021-01"),
        ],
    )
    with pytest.raises(CorpusError):
        dup.validate_integrity()
