# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A public, read-only MCP server that exposes Nima Karami's vetted, public-safe career corpus
(curated YAML) over Streamable HTTP. It powers a terminal-style portfolio chat: visitors ask
about his experience and request tailored resume drafts. Deployed on Fly.io at
`https://nima-career-mcp.fly.dev/mcp`.

Two non-negotiable invariants shape the design:
- **Honesty by construction.** Tools may only return values that exist in the corpus. The
  model selects/orders/tailors pre-approved material; it never authors facts, employers,
  dates, or metrics. Enforced in code, not just prompts.
- **Public, no secrets.** This repo holds server code + a public-safe corpus only.
  Application-tracking and private notes live in a separate private repo and must never
  appear here.

## Commands

```bash
uv sync --all-extras --dev                  # install (uv is the package manager)

uv run python scripts/verify.py             # the gate: format+lint+types+SAST+tests (== CI)

uv run pytest -q                            # all tests (includes corpus integrity)
uv run pytest tests/test_security.py -q     # one file
uv run pytest tests/test_tools.py::test_list_roles_includes_seed   # one test
uv run ruff check .                         # lint    (ruff format . to autofix style)
uv run pyright                              # types (checks src + tests)
uv run bandit -c pyproject.toml -r src/     # SAST

uv run nima-career-mcp                                  # stdio (local/desktop clients)
uv run nima-career-mcp --transport streamable-http      # HTTP at 127.0.0.1:8080/mcp
uv run python scripts/dump_corpus.py                    # dump raw + grouped + sample resumes
```

Inspector: `npx -y @modelcontextprotocol/inspector uv run nima-career-mcp` (or
`uv run mcp dev dev_server.py` — see `dev_server.py` for why the shim exists). Deploy:
`fly deploy`. CI runs `scripts/verify.py` (format+lint+types+SAST+tests) plus a Semgrep job
on push/PR. A pinned `pre-commit` hook (ruff check+format) is available: `pre-commit install`.

## Architecture

Data flows through one validation chokepoint, then a single logic layer, then thin adapters:

- **`corpus.py`** — Pydantic models + `load_corpus()` + `validate_integrity()`. Loads YAML
  from `corpus/` (override dir via `NIMA_CORPUS_DIR`) and **fails closed**: unresolved bullet
  `source_ids`, orphan references, or `company_id`/`org` disagreement raise at startup. This
  is what makes honesty-by-construction enforceable.
- **`service.py`** — `CareerService` holds all read/assembly logic and the response models.
  `assemble_resume` only copies corpus values and attaches `provenance` ids; the lone
  generative-looking path fills a corpus-approved summary template from corpus-derived fields.
  Treat this as the place to change behavior.
- **`tools/`, `resources.py`, `prompts.py`** — thin MCP registration over `CareerService`.
  `resources.py` serves `career://guidance` (the honesty/anti-injection rules a host should
  embed). Prompts and the mirror `career://` resources are stubbed opt-ins.
- **`search.py`** — deterministic ranking (rapidfuzz). The query is search *data*, never
  instructions — this is the anti-injection seam; keep it free of any eval/interpolation.
- **`grouping.py`** — roles are flat with a `company_id`; one company's title progression is
  reconstructed into tenures **at render time**, splitting on date gaps. So a leave-and-return
  is just two stints sharing a `company_id` — no schema change needed.
- **`server.py`** — wires `FastMCP` (stateless HTTP) and the middleware stack. The SDK's
  DNS-rebinding Host guard is deliberately disabled (it locks to localhost and 421s a real
  hostname); host/origin policy is owned by our middleware instead.
- **`security.py`** — raw ASGI middleware (rate limit, body-size cap, Origin + Host
  validation). Env-driven, "empty allowlist = public". Client IP comes from Fly's
  `Fly-Client-IP`, not the forgeable `X-Forwarded-For`. Config: `NIMA_ALLOWED_HOSTS`,
  `NIMA_ALLOWED_ORIGINS`, `NIMA_RATE_LIMIT_PER_MIN`, `NIMA_CORPUS_DIR`.

When adding a tool or corpus field, the path is: model in `corpus.py` (+ integrity check) →
logic + response model in `service.py` → registration in `tools/`. The corpus integrity test
and `test_assemble_resume.py` (asserts every emitted value traces to the corpus) guard the
honesty invariant — keep them passing.

## Conventions

- **Comments are minimal — only where the *why* isn't obvious from the code.** Do not narrate
  what the code already says. Prefer clear names over explanatory comments.
- Corpus content under `corpus/` is currently **placeholder**; the schema and evidence→bullet
  model are documented in `corpus/CORPUS.md`.
