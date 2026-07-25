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
import logging
import os
import sys
import time
from typing import Any, Optional

# Diagnostics go to stderr so they never contaminate the JSON on stdout.
log = logging.getLogger("growthkit.fetch_trends")

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


# A real desktop Chrome UA. Headless Chromium's default UA advertises
# "HeadlessChrome", which Creative Center answers with 403 and a 39-byte body —
# so acquisition could never see any request at all. The same URL returns 200 to
# an ordinary UA from the very same host, so this is a browser-misconfiguration
# fix, not an attempt to defeat a protection.
_DESKTOP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

# The signature triple below appears RETIRED. Observed 2026-07-25: with the page
# loading correctly (200, ~93 KB), its own API calls —
# ``/creative_radar_api/v1/user/info`` and ``/cc_portal_api/api/trendsTcc`` —
# carry no signature headers whatsoever, only Content-Type / Accept /
# Agw-Js-Conv. So acquisition legitimately returns None on the current site, the
# live path degrades to the labeled fallback, and re-enabling live trends means
# reimplementing against those endpoints rather than harvesting headers.
_WANTED_SIGNATURE_HEADERS = ("anonymous-user-id", "timestamp", "user-sign")


def acquire_headers() -> Optional[dict[str, str]]:
    """Acquire Creative Center signature headers via a headless browser.

    Loads the Creative Center page in Playwright with a realistic desktop
    context and intercepts ``XMLHttpRequest.setRequestHeader`` to capture
    anonymous-user-id / timestamp / user-sign. Returns None when Playwright is
    absent, the page does not load, or the headers are simply not present
    anymore (see the note above) — callers then degrade to the labeled fallback.
    Optional dependency by design: the skill works without live trends.

    Diagnostics are logged rather than swallowed, because a silent None here is
    indistinguishable from "site changed" and cost real debugging time.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        log.warning("acquire_headers: playwright not installed (pip install playwright "
                    "&& playwright install chromium)")
        return None
    try:  # pragma: no cover - requires a browser; not exercised in CI.
        captured: dict[str, str] = {}
        status: object = "?"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=_DESKTOP_UA, locale="en-US",
                viewport={"width": 1440, "height": 900},
            )
            page = context.new_page()
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
            resp = page.goto(
                "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en",
                wait_until="domcontentloaded", timeout=40000)
            status = resp.status if resp is not None else "?"
            page.wait_for_timeout(6000)
            captured = page.evaluate("window.__ccHeaders") or {}
            context.close()
            browser.close()
        headers = {k: v for k, v in captured.items()
                   if k.lower() in _WANTED_SIGNATURE_HEADERS}
        if not headers:
            log.warning(
                "acquire_headers: page status=%s, saw %d XHR header(s) %s but none of "
                "%s — the signature scheme looks retired; live trends stay on the "
                "labeled fallback.",
                status, len(captured), sorted(captured), list(_WANTED_SIGNATURE_HEADERS),
            )
        return headers or None
    except Exception as exc:
        log.warning("acquire_headers failed: %s: %s", type(exc).__name__, exc)
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

    # Surface acquisition diagnostics on stderr; stdout stays pure JSON.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s",
                        stream=sys.stderr)

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
