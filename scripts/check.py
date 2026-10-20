"""Run every quality check CI would run: lint, format, and the full test suite.

Run: python scripts/check.py

The test suite already regenerates data/ and outputs/ in a tmp dir and compares them with the
committed files, so this needs neither git nor a hosted CI runner.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECKS: list[tuple[str, list[str]]] = [
    ("ruff lint", [sys.executable, "-m", "ruff", "check", "."]),
    ("ruff format", [sys.executable, "-m", "ruff", "format", "--check", "."]),
    ("pytest", [sys.executable, "-m", "pytest", "-q"]),
]


def main() -> int:
    failed: list[str] = []
    for name, cmd in CHECKS:
        print(f"\n=== {name} ===", flush=True)
        start = time.perf_counter()
        code = subprocess.call(cmd, cwd=ROOT)
        print(f"--- {name}: {'ok' if code == 0 else 'FAILED'} ({time.perf_counter() - start:.1f}s)", flush=True)
        if code:
            failed.append(name)

    print("\nAll checks passed." if not failed else f"\nFailed: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
