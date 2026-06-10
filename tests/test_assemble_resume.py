"""The honesty guarantee, tested: assemble_resume emits only corpus-derived content."""

from __future__ import annotations

from nima_career_mcp.corpus import Corpus
from nima_career_mcp.service import CareerService


def _corpus_bullet_texts(corpus: Corpus) -> set[str]:
    return {b.text for b in corpus.all_bullets()}


def _all_corpus_ids(corpus: Corpus) -> set[str]:
    ids: set[str] = set(corpus.all_evidence_ids())
    ids |= {b.id for b in corpus.all_bullets()}
    ids |= {r.id for r in corpus.roles}
    ids |= {p.id for p in corpus.projects}
    return ids


def test_every_emitted_bullet_exists_in_corpus(service: CareerService, corpus: Corpus) -> None:
    draft = service.assemble_resume(focus="0-to-1 product")
    allowed = _corpus_bullet_texts(corpus)
    for role in draft.roles:
        for text in role.bullets:
            assert text in allowed, f"fabricated bullet: {text!r}"


def test_every_emitted_org_exists_in_corpus(service: CareerService, corpus: Corpus) -> None:
    draft = service.assemble_resume()
    orgs = {r.org for r in corpus.roles}
    for role in draft.roles:
        assert role.org in orgs, f"fabricated employer: {role.org!r}"


def test_provenance_is_populated_and_resolves(service: CareerService, corpus: Corpus) -> None:
    draft = service.assemble_resume(focus="realtime")
    assert draft.provenance, "expected provenance ids"
    known = _all_corpus_ids(corpus)
    for pid in draft.provenance:
        assert pid in known, f"provenance id not in corpus: {pid!r}"


def test_summary_is_template_derived(service: CareerService, corpus: Corpus) -> None:
    draft = service.assemble_resume(focus="product")
    # Summary must contain the approved headline (templates are filled from corpus values).
    assert corpus.profile.headline in draft.summary


def test_onepage_caps_bullets(service: CareerService) -> None:
    draft = service.assemble_resume(length="onepage")
    for role in draft.roles:
        assert len(role.bullets) <= 3


def test_markdown_render_contains_name(service: CareerService, corpus: Corpus) -> None:
    draft = service.assemble_resume(focus="design", format="markdown")
    assert draft.markdown is not None
    assert corpus.profile.name in draft.markdown
    assert draft.disclaimer  # the honesty note travels with the draft
