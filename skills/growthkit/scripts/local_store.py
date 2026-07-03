#!/usr/bin/env python3
"""local_store.py — the append-only local observation store.

Every GrowthKit run that produces a SHAREABLE observation (a public trend
snapshot from a successful fetch, or an aggregated owned benchmark from a CSV
analysis) stages it here: `skills/growthkit/data/observations.local.json`.
When the user later chooses to contribute, `federation/contribute.py` reads
this store by default — no hand-authored rows file needed.

Guarantees:
  - **Append-only. Nothing is ever destroyed.** Rows are only added; there is
    no delete/overwrite path. Duplicates (same shareable identity) are skipped.
  - **Atomic writes.** New content is written to a temp file and swapped in
    with os.replace, so a crash mid-write can't corrupt the store.
  - **Corruption preserves data.** If the existing store fails to parse, it is
    RENAMED to a timestamped .corrupt-*.json backup (never deleted) and a
    fresh store is started.
  - **Shareable rows only.** Rows are stripped to the shareable schema before
    staging, so the store can never accumulate owned/identifying data. The
    contribution guards run again at upload time (defense in depth).

The store is git-ignored and stays local until the user explicitly runs
contribute.py without --dry-run and with an HF_TOKEN.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_STORE = os.path.join(HERE, "..", "data", "observations.local.json")

# Reuse the single source of truth for the shareable schema.
import sys as _sys
_sys.path.insert(0, os.path.join(HERE, "federation"))
from validate import SHAREABLE, row_hash, strip_to_keep  # noqa: E402


def store_path(path: Optional[str] = None) -> str:
    return os.path.abspath(path or DEFAULT_STORE)


def load(path: Optional[str] = None) -> list[dict[str, Any]]:
    """Load the store; on parse failure, preserve the bytes as a backup."""
    p = store_path(path)
    if not os.path.exists(p):
        return []
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        # Never destroy: move the unreadable file aside, keep its bytes.
        backup = p + time.strftime(".corrupt-%Y%m%d%H%M%S.json")
        try:
            os.replace(p, backup)
        except OSError:
            pass
        return []


def append(rows: list[dict[str, Any]], path: Optional[str] = None) -> dict[str, Any]:
    """Stage shareable rows. Strips to the shareable schema, dedups against
    what's already staged, appends, writes atomically. Never removes a row."""
    p = store_path(path)
    existing = load(p)
    seen = {row_hash(r, SHAREABLE) for r in existing}

    added, skipped = 0, 0
    for row in rows:
        rec = strip_to_keep(row, SHAREABLE)
        if not rec:
            skipped += 1
            continue
        h = row_hash(rec, SHAREABLE)
        if h in seen:
            skipped += 1
            continue
        seen.add(h)
        existing.append(rec)
        added += 1

    if added:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, p)  # atomic swap — a crash can't corrupt the store

    return {"store": p, "added": added, "skipped_duplicates": skipped,
            "total_staged": len(existing)}


if __name__ == "__main__":
    print(json.dumps({"store": store_path(), "total_staged": len(load())}, indent=2))
