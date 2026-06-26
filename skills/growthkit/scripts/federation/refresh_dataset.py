#!/usr/bin/env python3
"""refresh_dataset.py — pull community data & refresh default benchmarks (FR20, §9F).

Pulls the shared Hugging Face dataset, validates each row (schema + range),
refuses the refresh if the corrupt ratio exceeds `max_corrupt_ratio`, no-ops if
fewer than `min_new_on_refresh` clean rows are available, then merges the clean
rows and rebuilds `benchmarks.json` defaults from aggregated community data.

HONESTY: a refreshed benchmark stays labeled with its source + evidence_type and
its confidence reflects segment coverage (LOW until a segment has enough rows).
Supports `--dry-run` (preview, no writes).

Usage:
    python3 refresh_dataset.py --dry-run
    python3 refresh_dataset.py --local rows.jsonl --dry-run   # validate a local file
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from typing import Any, Optional

# Single source of truth for schema/guards (stdlib-only), shared with the write
# side (contribute.py) and the auto-merge bot (automerge.py).
import validate as _v


def validate_row(row: Any) -> bool:
    """True iff the row is schema-valid, in-range, enum-valid, and PII-free."""
    ok, _reason = _v.validate_row(row, _v.GROWTHKIT_SCHEMA)
    return ok


def _parse_jsonl(text: str) -> list[Any]:
    """Parse a JSONL file. Unparseable lines count toward the corrupt ratio."""
    rows: list[Any] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"__corrupt__": True})  # counts toward corrupt ratio
    return rows


def _parse_file(text: str, filename: str) -> list[Any]:
    """Parse a contribution file. `.json` may be an array or a single object;
    `.jsonl` is one object per line. Append-only model => one file per
    contribution (pattern §3)."""
    if filename.endswith(".jsonl"):
        return _parse_jsonl(text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return [{"__corrupt__": True}]
    return payload if isinstance(payload, list) else [payload]


def partition(rows: list[Any]) -> tuple[list[dict[str, Any]], int]:
    """Split into (clean_rows, corrupt_count)."""
    clean: list[dict[str, Any]] = []
    corrupt = 0
    for r in rows:
        if isinstance(r, dict) and not r.get("__corrupt__") and validate_row(r):
            clean.append(r)
        else:
            corrupt += 1
    return clean, corrupt


def rebuild_benchmarks(clean_rows: list[dict[str, Any]], base: dict[str, Any]) -> dict[str, Any]:
    """Aggregate perf_benchmark rows by (industry, country, metric_name) into the
    community section of benchmarks.json. Confidence reflects coverage."""
    out = json.loads(json.dumps(base))  # deep copy
    community: dict[str, Any] = {}
    grouped: dict[tuple, list[float]] = {}
    for r in clean_rows:
        if r.get("data_type") != "perf_benchmark":
            continue
        key = (r["industry"], r["country"], r["metric_name"])
        grouped.setdefault(key, []).append(float(r["metric_value"]))

    for (industry, country, metric), values in grouped.items():
        seg = community.setdefault(f"{industry}|{country}", {})
        n = len(values)
        seg[metric] = {
            "median": round(statistics.median(values), 4),
            "n": n,
            "evidence_type": "measured",
            "source": "community_dataset",
            # Coverage-aware confidence: needs volume before it's trustworthy.
            "confidence": "MEDIUM" if n >= 10 else "LOW",
        }
    out.setdefault("community_benchmarks", {}).update(community)
    return out


def refresh(
    *,
    config: dict[str, Any],
    local_path: Optional[str] = None,
    dry_run: bool = True,
    benchmarks_path: Optional[str] = None,
) -> dict[str, Any]:
    fed = config.get("federation", {})
    min_new = fed.get("min_new_on_refresh", 50)
    max_corrupt = fed.get("max_corrupt_ratio", 0.25)
    dataset_id = fed.get("dataset_id", "Ahad690/growthkit-trends")

    # 1) Acquire rows (local file for testing/offline; else pull from HF).
    if local_path:
        with open(local_path, encoding="utf-8") as fh:
            rows = _parse_file(fh.read(), local_path)
        origin = f"local:{local_path}"
    else:
        rows, origin = _pull_from_hf(dataset_id)

    total = len(rows)
    clean, corrupt = partition(rows)
    corrupt_ratio = (corrupt / total) if total else 0.0

    report: dict[str, Any] = {
        "origin": origin,
        "dataset_id": dataset_id,
        "n_total": total,
        "n_clean": len(clean),
        "n_corrupt": corrupt,
        "corrupt_ratio": round(corrupt_ratio, 4),
        "max_corrupt_ratio": max_corrupt,
        "min_new": min_new,
        "dry_run": dry_run,
    }

    # 2) Refuse corrupt-heavy files.
    if total and corrupt_ratio > max_corrupt:
        report["status"] = "refused_too_corrupt"
        return report

    # 3) No-op below threshold.
    if len(clean) < min_new:
        report["status"] = "noop_below_min_new"
        return report

    # 4) Rebuild benchmarks.
    bpath = benchmarks_path or _default_benchmarks_path()
    with open(bpath, encoding="utf-8") as fh:
        base = json.load(fh)
    rebuilt = rebuild_benchmarks(clean, base)
    report["n_community_segments"] = len(rebuilt.get("community_benchmarks", {}))

    if dry_run:
        report["status"] = "dry_run_preview_only"
        report["preview_community_benchmarks"] = rebuilt.get("community_benchmarks", {})
        return report

    with open(bpath, "w", encoding="utf-8") as fh:
        json.dump(rebuilt, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    report["status"] = "merged"
    report["benchmarks_path"] = bpath
    return report


def _pull_from_hf(dataset_id: str) -> tuple[list[Any], str]:  # pragma: no cover - network
    """Download dataset contribution files from Hugging Face and parse them.

    Reads public data with NO token required. Handles both the content-addressed
    `contributions/*.json` files written by contribute.py and any legacy
    `*.jsonl` shards."""
    try:
        from huggingface_hub import HfApi, hf_hub_download  # type: ignore
    except Exception:
        return [], "hf_unavailable_no_huggingface_hub"
    try:
        token = os.environ.get("HF_TOKEN")  # optional; reads work unauthenticated
        api = HfApi(token=token)
        files = [f for f in api.list_repo_files(repo_id=dataset_id, repo_type="dataset")
                 if f.startswith("contributions/") and (f.endswith(".json") or f.endswith(".jsonl"))]
        rows: list[Any] = []
        for f in files:
            local = hf_hub_download(repo_id=dataset_id, filename=f, repo_type="dataset", token=token)
            with open(local, encoding="utf-8") as fh:
                rows.extend(_parse_file(fh.read(), f))
        return rows, f"hf:{dataset_id}"
    except Exception as e:
        return [], f"hf_error:{type(e).__name__}"


def _default_benchmarks_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "..", "references", "benchmarks.json")


def _load_config() -> dict[str, Any]:
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "..", "..", "references", "config.json"), encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Pull community data and refresh default benchmarks.")
    p.add_argument("--dry-run", action="store_true", help="Preview only; no writes")
    p.add_argument("--local", default=None, help="Validate/merge a local JSONL file instead of pulling HF")
    args = p.parse_args(argv)

    config = _load_config()
    report = refresh(config=config, local_path=args.local, dry_run=args.dry_run)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
