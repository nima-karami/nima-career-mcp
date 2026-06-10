# 0001 — Solidify the repo for human/agent collaboration

Date: 2026-06-09
Status: Accepted

## Context

The repo had ruff (lint only), pyright, and pytest wired into CI as separate steps, but no
formatting enforcement, no complexity/security lint rules, no pre-commit hook, no single
verify command, and no SAST. For a public, unauthenticated, internet-facing MCP server, the
missing security gate was the highest-value gap. A `/solidify-repo` audit scored the four
agent-readiness categories: instruction files **Pass**, deterministic checks **Weak**, verify
harness **Weak**, security gate **Missing**.

## Decision

Applied three of the four categories (instruction files left as-is — already high-signal):

1. **Deterministic checks.** Expanded ruff lint to `E,F,I,B,C901,S,UP,SIM`; enforced
   `ruff format`; added a pinned `.pre-commit-config.yaml` (ruff check+format, rev v0.15.16
   matching the dev-group ruff). Complexity ceiling **baselined at `max-complexity = 15`** to
   clear five inherently branchy, honesty-critical functions (corpus validator, resume
   assembler, markdown renderer, search, body-size middleware) rather than refactor vetted
   code to hit a number; >15 still fails. Trivial pre-existing violations (UP035, B905, SIM117)
   were fixed; all code reformatted.

2. **Security gate.** Added **Bandit** (pure-Python, Windows-native) to the dev group + the
   harness + CI, scoped to `src/` via `[tool.bandit]`. Added a **CI-only Semgrep** job
   (`p/python`, Linux container) for deeper taint analysis — Semgrep has no native Windows, so
   it cannot live in the local harness. Initial Bandit + ruff-`S` scans: zero findings.

3. **Verify harness.** Added `scripts/verify.py` — one cross-platform command
   (`uv run python scripts/verify.py`) running format → lint → types → SAST → tests, reporting
   all failures and exiting non-zero on any. CI now calls this same script as its gate so
   **local == CI**. `CLAUDE.md` updated to document it.

## Consequences

- One command (`scripts/verify.py`) reproduces the full CI gate locally; agents have a
  deterministic self-correction loop.
- The complexity ceiling is 15, not the stricter 10 — a deliberate baseline; revisit if those
  functions are later decomposed.
- Semgrep runs only in CI; local Windows runs rely on Bandit + ruff `S` rules for SAST.
- Contributors should run `pre-commit install` once to get pre-push formatting/linting.
- Category #1 (instruction files) was intentionally not modified.
