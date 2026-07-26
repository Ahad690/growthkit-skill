#!/usr/bin/env python3
"""fetch_youtube_trends.py — short-form benchmarks from the YouTube Data API.

A companion to `fetch_trends.py` (TikTok Creative Center), not a replacement.
Both stage into the same append-only local store; this one exists because it
rests on an **official, versioned, documented** API instead of an unversioned
private endpoint, so it keeps working unattended.

Why this is honest data, not an estimate:
  * Every figure is computed from `statistics` that YouTube itself returns for
    the videos currently on the `mostPopular` chart. Nothing is modelled.
  * What leaves the machine is only AGGREGATE (median/share) statistics plus the
    sample size. No video ids, urls, channels or per-video rows — the federation
    guard bans those fields outright, and aggregates are all a benchmark needs.
  * A median over the ~50 currently-trending videos in a region is exactly that
    and is labelled as such (`source: youtube_data_api`, `data_type:
    trending_benchmark`, plus an explicit `sample_size` row). It is NOT a claim
    about all videos on the platform.
  * No key, no network, or an API error => status is reported and NOTHING is
    staged. It never fabricates and never stages a fallback as an observation.

Usage:
    fetch_youtube_trends.py [--country US] [--category-id 0] [--max 50]
                            [--no-save] [--api-key KEY]

The key is read from --api-key, then $YOUTUBE_API_KEY, then a
`.youtube_key` file beside the repo root. Get one free at
https://console.cloud.google.com/apis/library/youtube.googleapis.com
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from typing import Any, Optional

try:  # requests is optional; absence => reported status, never a crash.
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore

API = "https://www.googleapis.com/youtube/v3/videos"

# A "short" for benchmarking purposes. YouTube Shorts are <= 3 minutes since the
# 2024 limit change; 60s is kept as a separate, stricter band because most
# short-form advice is still written for it.
SHORT_MAX_SECONDS = 180
CLASSIC_SHORT_SECONDS = 60

_ISO_DUR = re.compile(
    r"^P(?:(?P<days>\d+)D)?T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
)


def parse_iso_duration(value: str) -> Optional[int]:
    """ISO-8601 duration (e.g. 'PT1M30S') -> seconds, or None if unparseable."""
    if not isinstance(value, str):
        return None
    m = _ISO_DUR.match(value.strip())
    if not m:
        return None
    p = {k: int(v) for k, v in m.groupdict(default="0").items()}
    total = p["days"] * 86400 + p["hours"] * 3600 + p["minutes"] * 60 + p["seconds"]
    return total or None


def resolve_api_key(explicit: Optional[str] = None) -> Optional[str]:
    """--api-key -> $YOUTUBE_API_KEY -> `.youtube_key` file near the repo root."""
    if explicit:
        return explicit.strip()
    env = os.environ.get("YOUTUBE_API_KEY")
    if env:
        return env.strip()
    here = os.path.dirname(os.path.abspath(__file__))
    for up in ("../../..", "../../../..", "../.."):
        path = os.path.abspath(os.path.join(here, up, ".youtube_key"))
        if os.path.isfile(path):
            try:
                key = open(path, encoding="utf-8").read().strip()
                if key:
                    return key
            except OSError:
                pass
    return None


def _median(values: list[float]) -> Optional[float]:
    return statistics.median(values) if values else None


def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate the raw API items into shareable benchmark metrics.

    Rates are computed per video then medianed (not ratio-of-sums), so one
    mega-viral video cannot dominate the benchmark.
    """
    views: list[float] = []
    like_rates: list[float] = []
    comment_rates: list[float] = []
    durations: list[int] = []

    for it in items:
        st = it.get("statistics") or {}
        try:
            v = float(st.get("viewCount"))
        except (TypeError, ValueError):
            continue  # a video without a view count cannot anchor a rate
        if v <= 0:
            continue
        views.append(v)
        for key, bucket in (("likeCount", like_rates), ("commentCount", comment_rates)):
            try:  # these are absent when the uploader hides them — skip, never zero-fill
                bucket.append(float(st[key]) / v)
            except (KeyError, TypeError, ValueError):
                pass
        secs = parse_iso_duration(((it.get("contentDetails") or {}).get("duration") or ""))
        if secs:
            durations.append(secs)

    out: dict[str, Any] = {
        "sample_size": len(views),
        "view_count_median": _median(views),
        "like_rate_median": _median(like_rates),
        "comment_rate_median": _median(comment_rates),
        "engagement_rate_median": _median(
            [lr + cr for lr, cr in zip(like_rates, comment_rates)]
        ) if like_rates and comment_rates else None,
        "duration_seconds_median": _median([float(d) for d in durations]),
        # What share of what is trending is actually short-form? Directly useful
        # when deciding whether to invest in Shorts for a region.
        "short_form_share": (
            sum(1 for d in durations if d <= SHORT_MAX_SECONDS) / len(durations)
            if durations else None
        ),
        "sub_60s_share": (
            sum(1 for d in durations if d <= CLASSIC_SHORT_SECONDS) / len(durations)
            if durations else None
        ),
    }
    return out


def fetch_youtube_trends(
    country: str = "US",
    category_id: str = "0",
    max_results: int = 50,
    api_key: Optional[str] = None,
    timeout: int = 20,
) -> dict[str, Any]:
    """Fetch the mostPopular chart for a region and summarize it.

    Returns an envelope with `method` set to `youtube_data_api` ONLY on a real
    success; every failure path reports its reason and stages nothing.
    """
    key = resolve_api_key(api_key)
    base = {
        "platform": "youtube",
        "country": country,
        "category_id": category_id,
        "fetched_at": None,
        "metrics": {},
        "sources": ["youtube_data_api"],
    }
    if not key:
        return {**base, "method": "no_api_key", "flags": ["no_api_key"],
                "note": "Set $YOUTUBE_API_KEY (or write .youtube_key) to enable. "
                        "Nothing was fetched or staged."}
    if requests is None:
        return {**base, "method": "unavailable", "flags": ["requests_missing"],
                "note": "The requests package is not installed. Nothing staged."}

    params = {
        "part": "statistics,contentDetails",
        "chart": "mostPopular",
        "regionCode": country,
        "maxResults": max(1, min(int(max_results), 50)),
        "key": key,
    }
    if category_id and str(category_id) != "0":
        params["videoCategoryId"] = str(category_id)
    try:
        resp = requests.get(API, params=params, timeout=timeout)
        if resp.status_code != 200:
            # Surface the API's own reason (quota, bad region, invalid key).
            reason = ""
            try:
                reason = ((resp.json().get("error") or {}).get("message") or "")[:160]
            except Exception:
                pass
            return {**base, "method": "fetch_failed",
                    "flags": [f"http_{resp.status_code}"],
                    "note": reason or f"HTTP {resp.status_code}. Nothing staged."}
        items = resp.json().get("items") or []
    except Exception as exc:  # noqa: BLE001 - network/parse: report, never crash
        return {**base, "method": "fetch_failed",
                "flags": [f"reason:{type(exc).__name__}"],
                "note": str(exc)[:160]}

    if not items:
        return {**base, "method": "fetch_failed", "flags": ["empty_chart"],
                "note": "The chart returned no items. Nothing staged."}

    return {
        **base,
        "method": "youtube_data_api",
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metrics": summarize(items),
        "flags": [],
    }


def observations_from_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a successful fetch into shareable rows (§8.3 SHAREABLE schema).

    Only aggregate metrics are emitted — never a per-video row — so no banned
    field (video_id, url, handle, views, likes, comments) can ever appear.
    """
    if result.get("method") != "youtube_data_api":
        return []  # never stage a failure or fallback as an observation
    captured_on = (result.get("fetched_at") or "")[:10]
    industry = "all" if str(result.get("category_id", "0")) == "0" \
        else f"yt_category_{result.get('category_id')}"
    rows: list[dict[str, Any]] = []
    for name, value in (result.get("metrics") or {}).items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        rows.append({
            "platform": "youtube",
            "data_type": "trending_benchmark",
            "industry": industry,
            "country": result.get("country"),
            "metric_name": name,
            "metric_value": round(float(value), 6),
            # The mostPopular chart is a point-in-time snapshot, not a window.
            "period_days": 1,
            "captured_on": captured_on,
            "source": "youtube_data_api",
        })
    return rows


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Short-form benchmarks from the official YouTube Data API.")
    p.add_argument("--country", default="US", help="ISO region code (US, GB, DE...)")
    p.add_argument("--category-id", default="0",
                   help="YouTube videoCategoryId ('0' = all categories)")
    p.add_argument("--max", type=int, default=50, help="chart items to read (<=50)")
    p.add_argument("--api-key", default=None, help="else $YOUTUBE_API_KEY / .youtube_key")
    p.add_argument("--no-save", action="store_true",
                   help="do not stage successful observations in the local store")
    args = p.parse_args(argv)

    result = fetch_youtube_trends(
        country=args.country, category_id=args.category_id,
        max_results=args.max, api_key=args.api_key,
    )

    if result.get("method") == "youtube_data_api" and not args.no_save:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import local_store  # noqa: E402
        result["staged"] = local_store.append(observations_from_result(result))

    print(json.dumps(result, indent=2, ensure_ascii=False))
    # Non-zero only signals "no data collected", so a cron can log it plainly.
    return 0 if result.get("method") == "youtube_data_api" else 4


if __name__ == "__main__":
    sys.exit(main())
