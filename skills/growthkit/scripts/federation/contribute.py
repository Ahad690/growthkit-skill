#!/usr/bin/env python3
"""contribute.py — opt-in federation: share ONLY public anonymized data (FR18-FR19, §9F).

Collects public trend snapshots + anonymized aggregate benchmarks, whitelists
them to the shareable schema, dedups, and opens a Hugging Face dataset PR.

HARD GUARANTEE (P8): owned analytics, handles, account names, raw CSVs, and any
identifying/install-level field NEVER leave the machine. `assert_public_only`
aborts the whole contribution if ANY banned field is present — proven by
test_contribution_guard.py.

Contribution is OFF by default (N4/FR21): a real upload requires BOTH dropping
`--dry-run` AND an HF_TOKEN. No background upload, ever. Every run prints exactly
what would be shared.

Shareable row schema (§8.3):
  {platform, data_type, industry, country, metric_name, metric_value,
   period_days, captured_on, source}
For perf_benchmark rows, metric_value is AGGREGATED (e.g., median across the
contributor's posts) — never per-post, never with a video_id/handle/account.

Usage:
    python3 contribute.py --rows rows.json --dry-run        # preview only (default-safe)
    python3 contribute.py --rows rows.json                  # real PR (needs HF_TOKEN)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Any, Iterable, Optional

# Single source of truth for the schema/guards lives in validate.py (stdlib-only),
# shared with the auto-merge bot and the refresh/pull side.
from validate import BANNED as _BANNED_LIST
from validate import SHAREABLE as _SHAREABLE_LIST
from validate import VALID_DATA_TYPES as _VALID_DATA_TYPES
from validate import VALID_SOURCES as _VALID_SOURCES

SHAREABLE = set(_SHAREABLE_LIST)
BANNED = set(_BANNED_LIST)
VALID_DATA_TYPES = set(_VALID_DATA_TYPES)
VALID_SOURCES = set(_VALID_SOURCES)


def strip_to_shareable(row: dict[str, Any]) -> dict[str, Any]:
    """Keep ONLY the whitelisted shareable fields."""
    return {k: row[k] for k in SHAREABLE if k in row}


def assert_public_only(records: Iterable[dict[str, Any]]) -> None:
    """Abort if ANY record contains an identifying/owned field."""
    for rec in records:
        bad = BANNED & set(rec)
        if bad:
            raise ValueError(
                f"refusing to upload identifying/owned fields: {sorted(bad)}"
            )


def _row_key(rec: dict[str, Any]) -> tuple:
    return (
        rec.get("platform"), rec.get("data_type"), rec.get("industry"),
        rec.get("country"), rec.get("metric_name"), rec.get("period_days"),
        rec.get("captured_on"), rec.get("source"),
    )


def dedup(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for rec in records:
        k = _row_key(rec)
        if k not in seen:
            seen.add(k)
            out.append(rec)
    return out


def validate_shareable(rec: dict[str, Any]) -> list[str]:
    """Return a list of validation problems for a (already-stripped) record."""
    problems: list[str] = []
    required = {"platform", "data_type", "industry", "country", "metric_name",
                "metric_value", "captured_on", "source"}
    missing = required - set(rec)
    if missing:
        problems.append(f"missing:{sorted(missing)}")
    if rec.get("data_type") not in VALID_DATA_TYPES:
        problems.append(f"bad_data_type:{rec.get('data_type')}")
    if rec.get("source") not in VALID_SOURCES:
        problems.append(f"bad_source:{rec.get('source')}")
    mv = rec.get("metric_value")
    if mv is not None and not isinstance(mv, (int, float)):
        problems.append("metric_value_not_numeric")
    return problems


def build_contribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip → guard → dedup. Raises if any banned field survives (it won't)."""
    recs = [strip_to_shareable(r) for r in rows]
    # Guard the ORIGINAL rows too: a banned field present in the input must abort,
    # even though strip_to_shareable would have dropped it — defense in depth.
    assert_public_only(rows)
    assert_public_only(recs)
    return dedup(recs)


def contribute(
    rows: list[dict[str, Any]],
    *,
    dataset_id: str,
    dry_run: bool = True,
    hf_token_env: str = "HF_TOKEN",
) -> dict[str, Any]:
    """Preview (and optionally upload) a contribution. Default is dry-run."""
    cleaned = build_contribution(rows)
    problems = {i: p for i, p in
                ((i, validate_shareable(r)) for i, r in enumerate(cleaned)) if p}

    token = os.environ.get(hf_token_env)
    will_upload = (not dry_run) and bool(token)

    report = {
        "dataset_id": dataset_id,
        "n_input_rows": len(rows),
        "n_shareable_rows": len(cleaned),
        "shareable_rows": cleaned,
        "validation_problems": problems,
        "dry_run": dry_run,
        "has_token": bool(token),
        "will_upload": will_upload,
    }

    if dry_run:
        report["status"] = "dry_run_preview_only"
        return report
    if not token:
        report["status"] = "no_token_no_upload"
        report["note"] = f"Set ${hf_token_env} to upload. Nothing was sent."
        return report
    if problems:
        report["status"] = "validation_failed_no_upload"
        return report

    # Real upload path (token-gated). Append rows and open a PR.
    try:
        report.update(_open_hf_pr(cleaned, dataset_id, token))
        report["status"] = "pr_opened"
    except Exception as e:  # noqa: BLE001
        report["status"] = "upload_error"
        report["error"] = f"{type(e).__name__}: {e}"
    return report


def contribution_path(rows: list[dict[str, Any]], author: str) -> str:
    """Content-addressed, author-prefixed path. STACK, don't rewrite (pattern §3):
    one NEW file per contribution so PRs never collide or clobber existing data,
    and resubmitting identical data is idempotent (same hash -> same filename)."""
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]
    safe_author = "".join(c for c in (author or "anon") if c.isalnum() or c in "-_") or "anon"
    return f"contributions/{safe_author}-{digest}.json"


def _open_hf_pr(rows: list[dict[str, Any]], dataset_id: str, token: str) -> dict[str, Any]:  # pragma: no cover - network
    """Open a Hugging Face dataset PR adding ONE new content-addressed file.

    The file is a JSON array of the shareable rows. The auto-merge bot
    (automerge.py) merges it only if it is purely additive and clears the guard
    stack; otherwise it is held for a human. Append-only + git-versioned keeps
    the blast radius of any merge tiny and one corrective commit from gone."""
    from huggingface_hub import CommitOperationAdd, HfApi  # type: ignore

    api = HfApi(token=token)
    try:
        author = (api.whoami() or {}).get("name") or "anon"
    except Exception:  # noqa: BLE001
        author = "anon"
    path_in_repo = contribution_path(rows, author)
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    op = CommitOperationAdd(path_in_repo=path_in_repo, path_or_fileobj=payload.encode("utf-8"))
    commit = api.create_commit(
        repo_id=dataset_id,
        repo_type="dataset",
        operations=[op],
        commit_message=f"Add {len(rows)} anonymized trend/benchmark rows",
        create_pr=True,
    )
    return {"pr_url": getattr(commit, "pr_url", None), "path_in_repo": path_in_repo}


def _load_config_dataset_id() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(here, "..", "..", "references", "config.json")
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    fed = cfg.get("federation", {})
    return fed.get("dataset_id") or "Ahad690/growthkit-trends"


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Opt-in federation: contribute public anonymized rows.")
    p.add_argument("--rows", required=True, help="Path to a JSON array of candidate rows")
    p.add_argument("--dry-run", action="store_true", help="Preview only (default-safe; no upload)")
    p.add_argument("--dataset-id", default=None, help="Override the HF dataset id")
    args = p.parse_args(argv)

    with open(args.rows, encoding="utf-8") as fh:
        rows = json.load(fh)

    dataset_id = args.dataset_id or _load_config_dataset_id()
    try:
        report = contribute(rows, dataset_id=dataset_id, dry_run=args.dry_run)
    except ValueError as e:
        # assert_public_only tripped — refuse loudly, emit nothing.
        print(json.dumps({"status": "refused_identifying_fields", "error": str(e)}, indent=2))
        return 3

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
