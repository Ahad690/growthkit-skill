#!/usr/bin/env python3
"""fetch_trends.py — OPTIONAL Creative Center trend fetcher (FR10, §9B).

Best-effort trending hashtags (and best-effort sounds) for a country/industry
via TikTok's internal Creative Center endpoint. This is an OPTIONAL enrichment:

  - It REQUIRES signature headers acquired via a headless-browser step
    (see acquire_headers()) and works best behind a residential proxy.
  - It NEVER fabricates. On ANY failure (no headers, network error, empty
    response, bad status) it returns a clearly-labeled cached/community
    fallback — it never raises out of fetch_trending_hashtags() and never
    invents a trend.
  - It degrades gracefully: every other GrowthKit feature works fully with the
    network disabled. Owned-CSV analysis is the ground-truth layer (P2).

ToS NOTE: automating the Creative Center endpoint is operator responsibility and
may be against TikTok's terms. The skill surfaces this warning on first use.
`requests` is optional — if it is not installed, the fetcher degrades to the
labeled fallback instead of crashing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Optional

try:  # requests is optional; absence => graceful fallback, never a crash.
    import requests  # type: ignore
except Exception:  # pragma: no cover - environment dependent
    requests = None  # type: ignore

ENDPOINT = "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"

TOS_WARNING = (
    "[ToS notice] Fetching TikTok Creative Center trends automates an internal "
    "endpoint. This is best-effort, may break or be rate-limited, and is the "
    "operator's responsibility under TikTok's terms. A residential proxy is "
    "recommended. GrowthKit works fully without this — owned-CSV analysis is the "
    "ground-truth layer."
)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def fetch_trending_hashtags(
    country: str = "US",
    industry_id: str = "",
    period: int = 7,
    limit: int = 50,
    headers: Optional[dict[str, str]] = None,
    proxies: Optional[dict[str, str]] = None,
    cache: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Best-effort fetch. On any failure → labeled fallback (never raises/fabricates)."""
    params = {
        "page": 1, "limit": limit, "period": period, "country_code": country,
        "filter_by": "", "sort_by": "popular", "industry_id": industry_id,
    }
    try:
        if requests is None:
            raise RuntimeError("requests_not_installed")
        if not headers:
            raise RuntimeError("no_signature_headers")
        resp = requests.get(ENDPOINT, params=params, headers=headers, proxies=proxies, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
        items = (payload.get("data", {}) or {}).get("list", []) or []
        if not items:
            raise RuntimeError("empty_response")
        return {
            "items": [
                {
                    "hashtag": h.get("hashtag_name"),
                    "rank": h.get("rank"),
                    "publish_cnt": h.get("publish_cnt"),
                    "video_views": h.get("video_views"),
                }
                for h in items
            ],
            "country": country,
            "industry_id": industry_id,
            "confidence": "MEDIUM",
            "method": "creative_center_live",
            "sources": ["creative_center"],
            "flags": ["external_best_effort"],
            "fetched_at": _now_iso(),
        }
    except Exception as e:  # noqa: BLE001 — any failure must degrade, never crash.
        return _fallback(country, industry_id, cache, reason=type(e).__name__ + ":" + str(e))


def _fallback(country: str, industry_id: str, cache: Optional[dict[str, Any]], reason: str) -> dict[str, Any]:
    """Labeled cached/community fallback. Never fabricates trends."""
    key = f"{country}:{industry_id}"
    data = (cache or {}).get(key) if isinstance(cache, dict) else None
    return {
        "items": data or [],
        "country": country,
        "industry_id": industry_id,
        "confidence": "LOW",
        "method": "cache_or_community_fallback",
        "sources": ["community_dataset"],
        "flags": ["fetch_failed", f"reason:{reason}", "stale_possible"],
        "fetched_at": None,
    }


def acquire_headers() -> Optional[dict[str, str]]:
    """Acquire Creative Center signature headers via a headless browser.

    Runs the Creative Center page in Playwright and intercepts
    XMLHttpRequest.setRequestHeader to capture anonymous-user-id / timestamp /
    user-sign. Returns None if Playwright is not installed or acquisition fails
    — callers then degrade to the labeled fallback. Optional dependency by
    design (the skill works without live trends).
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        return None
    try:  # pragma: no cover - requires a browser; not exercised in CI.
        captured: dict[str, str] = {}
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.add_init_script(
                """
                const orig = XMLHttpRequest.prototype.setRequestHeader;
                window.__ccHeaders = {};
                XMLHttpRequest.prototype.setRequestHeader = function(k, v) {
                    try { window.__ccHeaders[k] = v; } catch (e) {}
                    return orig.apply(this, arguments);
                };
                """
            )
            page.goto("https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en",
                      wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)
            captured = page.evaluate("window.__ccHeaders") or {}
            browser.close()
        wanted = ("anonymous-user-id", "timestamp", "user-sign")
        headers = {k: v for k, v in captured.items() if k.lower() in wanted}
        return headers or None
    except Exception:
        return None


def _cache_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "data", "trends.cache.json")


def _load_cache() -> dict[str, Any]:
    path = _cache_path()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict[str, Any], result: dict[str, Any]) -> None:
    """Persist a successful live fetch so future failures have a real fallback.
    Merges into the existing cache (never truncates other keys); atomic write."""
    if result.get("method") != "creative_center_live" or not result.get("items"):
        return
    key = f"{result.get('country')}:{result.get('industry_id', '')}"
    cache = dict(cache or {})
    cache[key] = result["items"]
    cache[f"{key}:fetched_at"] = result.get("fetched_at")
    path = _cache_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def observations_from_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a successful live fetch into shareable observation rows
    (§8.3 schema) for the append-only local store. The hashtag is encoded in
    metric_name since the shareable schema has no free-form tag field."""
    if result.get("method") != "creative_center_live":
        return []  # never stage fallback/cached data as a fresh observation
    captured_on = (result.get("fetched_at") or "")[:10]
    industry = result.get("industry_id") or "all"
    rows: list[dict[str, Any]] = []
    for item in result.get("items", []):
        tag = item.get("hashtag")
        if not tag:
            continue
        for metric in ("publish_cnt", "video_views"):
            value = item.get(metric)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                rows.append({
                    "platform": "tiktok",
                    "data_type": "hashtag_trend",
                    "industry": industry,
                    "country": result.get("country"),
                    "metric_name": f"{metric}:{tag}",
                    "metric_value": value,
                    "period_days": result.get("period_days", 7),
                    "captured_on": captured_on,
                    "source": "creative_center",
                })
    return rows


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Optional Creative Center trend fetcher (best-effort).")
    p.add_argument("--country", default="US")
    p.add_argument("--industry-id", default="")
    p.add_argument("--period", type=int, default=7)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--acquire-headers", action="store_true",
                   help="Attempt Playwright header acquisition (optional dependency)")
    p.add_argument("--no-warning", action="store_true", help="Suppress the ToS warning line")
    p.add_argument("--no-save", action="store_true",
                   help="Skip persisting a successful fetch to the local cache/store")
    args = p.parse_args(argv)

    if not args.no_warning:
        print(TOS_WARNING, file=sys.stderr)

    headers = acquire_headers() if args.acquire_headers else None
    cache = _load_cache()
    result = fetch_trending_hashtags(
        country=args.country, industry_id=args.industry_id,
        period=args.period, limit=args.limit, headers=headers, cache=cache,
    )
    result["period_days"] = args.period

    # Persist every successful run (append-only; nothing is ever destroyed):
    # the cache powers future fallbacks, the store stages shareable rows the
    # user may contribute to the community dataset later.
    if not args.no_save and result.get("method") == "creative_center_live":
        _save_cache(cache, result)
        import local_store
        result["staged"] = local_store.append(observations_from_result(result))

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0  # Always 0: a labeled fallback is a successful, honest outcome.


if __name__ == "__main__":
    sys.exit(main())
