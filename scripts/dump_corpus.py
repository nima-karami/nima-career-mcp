"""Dump the loaded corpus and key derived views — a quick way to eyeball/test the data.

Run it with:  uv run python scripts/dump_corpus.py
"""

from __future__ import annotations

import sys

from nima_career_mcp.corpus import load_corpus
from nima_career_mcp.service import CareerService


def _h(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def main() -> None:
    # Ensure en-dashes etc. print cleanly regardless of console codepage.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    corpus = load_corpus()
    svc = CareerService(corpus)

    _h("RAW CORPUS (the database: profile + roles w/ evidence+bullets + projects + skills)")
    print(corpus.model_dump_json(indent=2))

    _h("EXPERIENCE — grouped into company tenures (newest first)")
    print(svc.list_experience().model_dump_json(indent=2))

    _h("SAMPLE RESUME — focus='backend' (markdown)")
    print(svc.assemble_resume(focus="backend", format="markdown").markdown)

    _h("SAMPLE RESUME — full, no focus (markdown)")
    print(svc.assemble_resume(format="markdown").markdown)


if __name__ == "__main__":
    main()
