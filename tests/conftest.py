from __future__ import annotations

import pytest

from nima_career_mcp.corpus import Corpus, load_corpus
from nima_career_mcp.service import CareerService


@pytest.fixture
def anyio_backend() -> str:
    # Run async tests on asyncio only (not trio).
    return "asyncio"


@pytest.fixture(scope="session")
def corpus() -> Corpus:
    return load_corpus()


@pytest.fixture
def service(corpus: Corpus) -> CareerService:
    return CareerService(corpus)
