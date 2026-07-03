#!/usr/bin/env python3
"""analyze_studio_csv.py — GROUND-TRUTH layer (FR9, §9A).

Ingest a TikTok Studio / Business Suite content export (CSV) and compute, per
post: completion rate, avg watch-time %, share/save/profile-visit rate, and a
traffic-source mix. Rank winners by completion and flag hook failures (avg
watch < the 3-second-view floor).

HONESTY (P1/P2/P3): every number here is computed from the founder's OWN export
(the reliable ground-truth layer). Outputs carry confidence=HIGH ONLY for
directly-observed owned facts, method="owned_studio_csv", sources=["owned_csv"].
The model never invents these numbers — this script does, from real data.

The analyzer is tolerant of column-name variants and missing columns: it
computes what it can and flags the rest. Raw CSV stays local; never federated.

Usage:
    python3 analyze_studio_csv.py path/to/export.csv [--floor 0.20] [--top-n 10]
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from typing import Any, Optional

# Tolerant column-name resolution: canonical -> accepted variants (lowercased).
COLUMN_ALIASES: dict[str, list[str]] = {
    "video_id": ["video_id", "video id", "id", "post_id", "post id"],
    "post_date": ["post_date", "post date", "date", "create_time", "published", "publish_date"],
    "views": ["views", "video_views", "video views", "play", "plays", "play_count"],
    "total_play_time_sec": ["total_play_time_sec", "total play time", "total_play_time", "total watch time"],
    "video_duration_sec": ["video_duration_sec", "video duration", "duration", "duration_sec", "video_duration"],
    "avg_watch_time_sec": ["avg_watch_time_sec", "average watch time", "avg watch time", "avg_watch_time", "average_watch_time"],
    "full_video_watch_rate": ["full_video_watch_rate", "completion rate", "completion_rate", "full video watch rate", "watched full video", "complete_play_rate"],
    "likes": ["likes", "like", "like_count", "hearts"],
    "comments": ["comments", "comment", "comment_count"],
    "shares": ["shares", "share", "share_count"],
    "saves": ["saves", "save", "favorites", "favourites", "save_count"],
    "profile_visits": ["profile_visits", "profile visits", "profile_views", "profile view"],
    "traffic_source_breakdown": ["traffic_source_breakdown", "traffic source", "traffic_source", "traffic sources"],
}


def _f(x: Any) -> Optional[float]:
    """Parse a possibly-messy numeric cell (handles %, commas, blanks)."""
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.lower() in ("n/a", "na", "-", "--"):
        return None
    s = s.replace("%", "").replace(",", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _round(x: Optional[float], ndigits: int = 4) -> Optional[float]:
    return round(x, ndigits) if x is not None else None


def _build_resolver(fieldnames: list[str]) -> dict[str, Optional[str]]:
    """Map each canonical column to the actual header present (or None)."""
    lowered = {fn.strip().lower(): fn for fn in (fieldnames or [])}
    resolver: dict[str, Optional[str]] = {}
    for canonical, variants in COLUMN_ALIASES.items():
        found: Optional[str] = None
        for v in variants:
            if v in lowered:
                found = lowered[v]
                break
        resolver[canonical] = found
    return resolver


def _get(row: dict[str, Any], resolver: dict[str, Optional[str]], canonical: str) -> Any:
    actual = resolver.get(canonical)
    return row.get(actual) if actual else None


def _normalize_rate(x: Optional[float]) -> Optional[float]:
    """A completion/watch rate may be expressed as 0-1 or 0-100. Normalize to 0-1."""
    if x is None:
        return None
    return x / 100.0 if x > 1.0 else x


def analyze(path: str, three_sec_floor: float = 0.20, top_n: int = 10) -> dict[str, Any]:
    """Analyze a TikTok Studio CSV export. Returns a structured, provenance-tagged result."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = reader.fieldnames or []
            rows = list(reader)
    except FileNotFoundError:
        return {
            "posts": [], "top_by_completion": [], "n_hook_failures": 0,
            "error": f"file_not_found: {path}",
            "confidence": "NONE", "method": "owned_studio_csv", "sources": ["owned_csv"],
            "flags": ["missing_data"],
        }

    resolver = _build_resolver(fieldnames)
    missing_cols = [c for c, actual in resolver.items() if actual is None and not c.startswith("_")]

    out: list[dict[str, Any]] = []
    for r in rows:
        dur = _f(_get(r, resolver, "video_duration_sec"))
        awt = _f(_get(r, resolver, "avg_watch_time_sec"))
        views = _f(_get(r, resolver, "views"))
        shares = _f(_get(r, resolver, "shares"))
        saves = _f(_get(r, resolver, "saves"))
        profile_visits = _f(_get(r, resolver, "profile_visits"))
        completion = _normalize_rate(_f(_get(r, resolver, "full_video_watch_rate")))

        watch_pct = (awt / dur) if (awt is not None and dur not in (None, 0)) else None

        flags: list[str] = []
        if watch_pct is not None and watch_pct < three_sec_floor:
            flags.append("hook_failure")
        # Per-row provenance is HIGH only when the post had observable data.
        row_confidence = "HIGH" if views is not None else "LOW"
        if views is None:
            flags.append("missing_views")

        out.append({
            "video_id": _get(r, resolver, "video_id"),
            "post_date": _get(r, resolver, "post_date"),
            "views": views,
            "video_duration_sec": dur,
            "avg_watch_time_sec": awt,
            "completion_rate": _round(completion),
            "watch_time_pct": _round(watch_pct),
            "share_rate": _round(shares / views) if (shares is not None and views) else None,
            "save_rate": _round(saves / views) if (saves is not None and views) else None,
            "profile_visit_rate": _round(profile_visits / views) if (profile_visits is not None and views) else None,
            "traffic_source_breakdown": _get(r, resolver, "traffic_source_breakdown"),
            "flags": flags,
            "confidence": row_confidence,
            "method": "owned_studio_csv",
            "sources": ["owned_csv"],
        })

    winners = sorted(
        [o for o in out if o["completion_rate"] is not None],
        key=lambda o: o["completion_rate"],
        reverse=True,
    )[:top_n]

    result_flags: list[str] = []
    if missing_cols:
        result_flags.append("missing_columns:" + ",".join(sorted(missing_cols)))
    if not out:
        result_flags.append("no_rows")

    return {
        "posts": out,
        "top_by_completion": winners,
        "n_posts": len(out),
        "n_hook_failures": sum(1 for o in out if "hook_failure" in o["flags"]),
        "three_sec_floor": three_sec_floor,
        "confidence": "HIGH" if out else "NONE",
        "method": "owned_studio_csv",
        "sources": ["owned_csv"],
        "flags": result_flags,
    }


def aggregate_benchmarks(result: dict[str, Any], industry: str, country: str,
                         captured_on: Optional[str] = None,
                         min_posts: int = 3) -> list[dict[str, Any]]:
    """Turn an analysis into AGGREGATED perf_benchmark rows (§8.3 schema) for
    the append-only local store. Medians across posts only — never per-post,
    never a video_id/handle. Requires >= min_posts posts with data so a single
    post can't masquerade as a benchmark. Raw CSV data itself never leaves."""
    posts = result.get("posts") or []
    captured_on = captured_on or time.strftime("%Y-%m-%d")
    rows: list[dict[str, Any]] = []
    for metric in ("completion_rate", "watch_time_pct", "share_rate", "save_rate"):
        values = [p[metric] for p in posts
                  if isinstance(p.get(metric), (int, float)) and not isinstance(p.get(metric), bool)]
        if len(values) >= min_posts:
            rows.append({
                "platform": "tiktok",
                "data_type": "perf_benchmark",
                "industry": industry,
                "country": country,
                "metric_name": f"{metric}_median",
                "metric_value": round(statistics.median(values), 4),
                "period_days": 7,
                "captured_on": captured_on,
                "source": "aggregated_owned",
            })
    return rows


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Analyze a TikTok Studio CSV export (ground-truth layer).")
    p.add_argument("csv_path", help="Path to the TikTok Studio / Business Suite content export CSV")
    p.add_argument("--floor", type=float, default=0.20, help="3-second-view (hook-failure) floor, 0-1")
    p.add_argument("--top-n", type=int, default=10, help="Number of winners to return by completion rate")
    p.add_argument("--industry", help="Industry label — with --country, stages aggregated "
                                      "(median-only) benchmark rows in the local store")
    p.add_argument("--country", help="Country code — see --industry")
    p.add_argument("--no-save", action="store_true", help="Skip staging aggregated benchmarks")
    args = p.parse_args(argv)
    result = analyze(args.csv_path, three_sec_floor=args.floor, top_n=args.top_n)

    # Stage AGGREGATED medians (only) in the append-only local store so the
    # user can contribute them later. Per-post rows and the raw CSV stay local
    # and are never staged.
    if (not args.no_save and not result.get("error")
            and args.industry and args.country):
        import local_store
        rows = aggregate_benchmarks(result, args.industry, args.country)
        if rows:
            result["staged"] = local_store.append(rows)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not result.get("error") else 1


if __name__ == "__main__":
    sys.exit(main())
