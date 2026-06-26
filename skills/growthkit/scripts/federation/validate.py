#!/usr/bin/env python3
"""validate.py — GrowthKit federation validation + merge gates (stdlib only).

Single source of truth for the shareable schema, the banned/PII field set, and
the layered guard stack used by BOTH the write side (contribute.py) and the
auto-merge bot (automerge.py) / pull side (refresh_dataset.py).

Three things live here:
  1. Per-row schema / PII / range / enum validation -> validate_row / partition
  2. The merge/no-op/abort gate (corrupt ratio)       -> decide
  3. Optional anti-abuse heuristics                   -> abuse_scan

Everything is driven by the SCHEMA / ABUSE config dicts so the domain lives in
config, not code. Pure stdlib (json, hashlib, statistics) — no pip installs, so
it runs anywhere and stays trivially auditable.
"""
from __future__ import annotations

import hashlib
import statistics
from typing import Any

# --------------------------------------------------------------------------
# GrowthKit domain config (the only place the schema is defined)
# --------------------------------------------------------------------------

# The ONLY fields that may leave a contributor's machine (§8.3).
SHAREABLE = [
    "platform", "data_type", "industry", "country", "metric_name",
    "metric_value", "period_days", "captured_on", "source",
]

# Any of these in a record => refuse the entire contribution (P8).
BANNED = [
    "video_id", "handle", "account", "account_name", "username", "url",
    "raw_csv", "profile_visits", "install_id", "device_id", "email",
    "ip", "ip_address", "user_id", "post_id", "views", "likes", "comments",
]

VALID_DATA_TYPES = ["hashtag_trend", "sound_trend", "perf_benchmark"]
VALID_SOURCES = ["creative_center", "aggregated_owned"]

GROWTHKIT_SCHEMA: dict[str, Any] = {
    "keep": SHAREABLE,
    "required_str": ["platform", "data_type", "industry", "country",
                     "metric_name", "captured_on", "source"],
    "numeric": {"metric_value": {"min": 0}, "period_days": {"min": 1, "max": 365}},
    "list_fields": [],
    "enum": {"data_type": VALID_DATA_TYPES, "source": VALID_SOURCES,
             "platform": ["tiktok"]},
    "forbidden": BANNED,
}

GROWTHKIT_ABUSE: dict[str, Any] = {
    "dedup_key": SHAREABLE,                       # full-row identity for dedup
    "min_unique_ratio": 0.5,
    "dedup_min_rows": 5,
    "ordering": [],                               # no ordered tiers in this schema
    # A group's median metric_value shouldn't be wildly off the trusted reference.
    "outlier": {"field": "metric_value", "group_by": "metric_name",
                "factor": 50, "min_rows": 3},
}


# --------------------------------------------------------------------------
# 1. Per-row validation
# --------------------------------------------------------------------------

def validate_row(row: Any, schema: dict[str, Any] = GROWTHKIT_SCHEMA) -> tuple[bool, str]:
    """Return (ok, reason). Enforces shape, ranges, enums, list types, no-PII."""
    if not isinstance(row, dict):
        return False, "not an object"
    for bad in schema.get("forbidden", []):
        if bad in row:
            return False, f"forbidden/PII field present: {bad}"
    for field in schema.get("required_str", []):
        v = row.get(field)
        if not (isinstance(v, str) and v.strip()):
            return False, f"missing {field}"
    for field, allowed in schema.get("enum", {}).items():
        if row.get(field) not in allowed:
            return False, f"{field} not in {allowed}"
    for field, bounds in schema.get("numeric", {}).items():
        v = row.get(field)
        if v is None:
            continue
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            return False, f"{field} not number-or-null"
        if "min" in bounds and v < bounds["min"]:
            return False, f"{field} below min {bounds['min']}"
        if "max" in bounds and v > bounds["max"]:
            return False, f"{field} above max {bounds['max']}"
    for field in schema.get("list_fields", []):
        v = row.get(field)
        if v is not None and not isinstance(v, list):
            return False, f"{field} not a list"
    return True, "ok"


def strip_to_keep(row: dict[str, Any], keep: list[str]) -> dict[str, Any]:
    """Rebuild a row from the keep-list only (drops any stray/PII field)."""
    return {k: row[k] for k in keep if k in row}


def partition(rows: list[Any], schema: dict[str, Any] = GROWTHKIT_SCHEMA):
    """Split rows into (valid_and_canonicalized, invalid_reasons)."""
    keep = schema.get("keep", [])
    valid, invalid = [], []
    for row in rows:
        ok, reason = validate_row(row, schema)
        if ok:
            valid.append(strip_to_keep(row, keep) if keep else row)
        else:
            invalid.append(reason)
    return valid, invalid


def row_hash(row: dict[str, Any], key_fields: list[str]) -> str:
    """Stable hash over selected fields, for dedup."""
    parts = [str(row.get(f, "")).strip().lower() for f in key_fields]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def dedup_count(rows: list[dict[str, Any]], key_fields: list[str]) -> int:
    seen, n = set(), 0
    for r in rows:
        h = row_hash(r, key_fields)
        if h not in seen:
            seen.add(h)
            n += 1
    return n


# --------------------------------------------------------------------------
# 2. The merge gate
# --------------------------------------------------------------------------

def decide(seen: int, invalid_count: int, new_after_dedup: int,
           min_new: int, max_corrupt_ratio: float, file_errors: int) -> dict[str, str]:
    """Verdict for a batch. Returns {action: merge|noop|abort, status, reason}."""
    if file_errors:
        return {"action": "abort", "status": "corrupt",
                "reason": f"{file_errors} file(s) failed to parse"}
    if seen == 0:
        return {"action": "noop", "status": "empty", "reason": "no rows found"}
    ratio = invalid_count / seen
    if ratio > max_corrupt_ratio:
        return {"action": "abort", "status": "corrupt",
                "reason": f"corrupt fraction {ratio:.0%} > {max_corrupt_ratio:.0%} "
                          f"({invalid_count}/{seen})"}
    if new_after_dedup < min_new:
        return {"action": "noop", "status": "insufficient",
                "reason": f"only {new_after_dedup} new row(s); need >= {min_new}"}
    return {"action": "merge", "status": "ok",
            "reason": f"{new_after_dedup} clean new row(s)"}


# --------------------------------------------------------------------------
# 3. Optional anti-abuse heuristics (well-formed-but-suspicious data)
# --------------------------------------------------------------------------

def abuse_scan(rows: list[dict[str, Any]], reference_rows: list[dict[str, Any]],
               abuse: dict[str, Any]) -> list[str]:
    """Return a list of reasons ([] = clean). Each check runs only if configured."""
    reasons: list[str] = []
    if not rows or not abuse:
        return reasons

    key = abuse.get("dedup_key")
    if key and len(rows) >= abuse.get("dedup_min_rows", 5):
        uniq = dedup_count(rows, key)
        if uniq / len(rows) < abuse.get("min_unique_ratio", 0.5):
            reasons.append(f"only {uniq}/{len(rows)} unique rows (flooding)")

    order = abuse.get("ordering")
    if order:
        viol = 0
        for r in rows:
            seq = [r.get(f) for f in order if isinstance(r.get(f), (int, float))]
            if len(seq) >= 2 and any(a > b for a, b in zip(seq, seq[1:])):
                viol += 1
        if viol / len(rows) > abuse.get("ordering_violation_max_ratio", 0.3):
            reasons.append(f"{viol}/{len(rows)} rows violate ascending {order}")

    out = abuse.get("outlier")
    if out and reference_rows:
        field, group = out["field"], out["group_by"]
        factor, min_rows = out.get("factor", 10), out.get("min_rows", 3)
        ref = _group_medians(reference_rows, group, field)
        cur = _group_values(rows, group, field)
        for g, vals in cur.items():
            if g in ref and ref[g] > 0 and len(vals) >= min_rows:
                r = statistics.median(vals) / ref[g]
                if r > factor or r < 1 / factor:
                    reasons.append(f"group '{g}' {field} median is {r:.1f}x reference (outlier)")
    return reasons


def _group_values(rows, group, field):
    out: dict[Any, list[float]] = {}
    for r in rows:
        g, v = r.get(group), r.get(field)
        if g is not None and isinstance(v, (int, float)) and not isinstance(v, bool):
            out.setdefault(g, []).append(v)
    return out


def _group_medians(rows, group, field):
    return {g: statistics.median(v) for g, v in _group_values(rows, group, field).items() if v}


if __name__ == "__main__":  # tiny smoke test
    good = {"platform": "tiktok", "data_type": "hashtag_trend", "industry": "saas",
            "country": "US", "metric_name": "publish_cnt", "metric_value": 1000,
            "period_days": 7, "captured_on": "2026-06-01", "source": "creative_center"}
    assert validate_row(good)[0]
    assert not validate_row(dict(good, handle="@x"))[0]            # PII
    assert not validate_row(dict(good, metric_value=-1))[0]         # range
    assert not validate_row(dict(good, data_type="nope"))[0]        # enum
    v, inv = partition([good, {"platform": "tiktok"}])
    assert len(v) == 1 and len(inv) == 1
    assert decide(10, 0, 8, 1, 0.0, 0)["action"] == "merge"
    assert decide(10, 1, 9, 1, 0.0, 0)["action"] == "abort"        # any invalid at ratio 0
    print("validate.py self-test OK")
