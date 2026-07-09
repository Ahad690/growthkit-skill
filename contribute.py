#!/usr/bin/env python3
"""One-command, opt-in contribution to the community trend/benchmark dataset.

    python contribute.py            # preview + (after a one-time token setup) open a PR
    python contribute.py --dry-run  # preview only; upload nothing

Thin wrapper over the skill's federation contribute script. It reads the
append-only local observation store staged by your fetch/analysis runs, guides a
one-time Hugging Face token setup the first time (then never asks again; --token
accepts a paste), previews the PII-guarded rows, and opens a PR only on an
explicit run with your token. No background sync.
"""
from __future__ import annotations

import pathlib
import sys

_FED = pathlib.Path(__file__).parent / "skills" / "growthkit" / "scripts" / "federation"
sys.path.insert(0, str(_FED))

from contribute import main  # noqa: E402  (skill script on the path above)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
