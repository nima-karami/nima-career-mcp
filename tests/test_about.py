"""get_about: the voice/fact facets (languages, interests, education, principles)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from nima_career_mcp.corpus import (
    Corpus,
    CorpusError,
    Education,
    Interest,
    Language,
    Principle,
    Profile,
    load_corpus,
)
from nima_career_mcp.service import CareerService


def test_get_about_returns_all_four_facets() -> None:
    service = CareerService(
        Corpus(
            profile=Profile(name="Test"),
            languages=[
                Language(name="Persian (Farsi)", proficiency="native", note="mother tongue")
            ],
            interests=[Interest(name="Chess", note="long-game calculation")],
            education=[Education(id="march", institution="School", degree="M.Arch")],
            principles=[Principle(id="clarity", title="Clarity from mess", body="hold it")],
        )
    )
    about = service.get_about()
    assert [lang.name for lang in about.languages] == ["Persian (Farsi)"]
    assert about.languages[0].note == "mother tongue"
    assert about.interests[0].name == "Chess"
    assert about.education[0].degree == "M.Arch"
    assert about.principles[0].title == "Clarity from mess"


def test_get_about_empty_when_unpopulated() -> None:
    about = CareerService(Corpus(profile=Profile(name="Test"))).get_about()
    assert about.languages == []
    assert about.interests == []
    assert about.education == []
    assert about.principles == []


def test_load_corpus_reads_about_files(tmp_path: Path) -> None:
    (tmp_path / "profile.yaml").write_text("name: Test\n", encoding="utf-8")
    (tmp_path / "languages.yaml").write_text(
        yaml.safe_dump([{"name": "English", "proficiency": "fluent", "note": "working language"}]),
        encoding="utf-8",
    )
    (tmp_path / "interests.yaml").write_text(
        yaml.safe_dump([{"name": "Beach volleyball", "note": "flow"}]), encoding="utf-8"
    )
    (tmp_path / "education.yaml").write_text(
        yaml.safe_dump([{"id": "march", "institution": "U", "degree": "M.Arch"}]),
        encoding="utf-8",
    )
    (tmp_path / "principles.yaml").write_text(
        yaml.safe_dump([{"id": "p1", "title": "Clarity", "body": "x"}]), encoding="utf-8"
    )
    c = load_corpus(tmp_path)
    assert c.languages[0].name == "English"
    assert c.interests[0].note == "flow"
    assert c.education[0].degree == "M.Arch"
    assert c.principles[0].title == "Clarity"


def test_integrity_rejects_duplicate_education_ids() -> None:
    dup = Corpus(
        profile=Profile(name="Test"),
        education=[
            Education(id="e", institution="A", degree="X"),
            Education(id="e", institution="B", degree="Y"),
        ],
    )
    with pytest.raises(CorpusError):
        dup.validate_integrity()


def test_integrity_rejects_duplicate_principle_ids() -> None:
    dup = Corpus(
        profile=Profile(name="Test"),
        principles=[Principle(id="p", title="A"), Principle(id="p", title="B")],
    )
    with pytest.raises(CorpusError):
        dup.validate_integrity()
