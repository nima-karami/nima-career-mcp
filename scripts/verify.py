#!/usr/bin/env python
"""One-command verify gate: format, lint, types, SAST, tests.

Runs every check (so you see all failures, not just the first), then exits non-zero
if any failed. Run with: uv run python scripts/verify.py
"""

from __future__ import annotations

import subprocess
import sys

CHECKS: list[tuple[str, list[str]]] = [
    ("format", ["ruff", "format", "--check", "."]),
    ("lint", ["ruff", "check", "."]),
    ("types", ["pyright"]),
    ("sast", ["bandit", "-c", "pyproject.toml", "-q", "-r", "src/"]),
    ("tests", ["pytest", "-q"]),
]


def main() -> int:
    failed: list[str] = []
    for name, cmd in CHECKS:
        print(f"\n=== {name}: {' '.join(cmd)} ===", flush=True)
        if subprocess.run(cmd).returncode != 0:  # noqa: S603 (cmds are hardcoded constants)
            failed.append(name)

    print("\n" + "=" * 40)
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
