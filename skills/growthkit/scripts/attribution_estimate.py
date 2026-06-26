#!/usr/bin/env python3
"""attribution_estimate.py — banded organic-install attribution (FR13, §9D).

Organic-TikTok install attribution is STRUCTURALLY approximate (there is no
pixel on organic posts). This script triangulates the founder's OWN signals —
UTM/landing-page installs, promo-code redemptions, MMP organic bucket,
brand-search lift, and survey share — into a BANDED estimate with a confidence
label. It NEVER returns a single precise number, and it surfaces the
"deferred deep links are not reliable for attribution" caveat (P4).

HONESTY: when no usable signal is supplied, returns confidence="NONE" and
flag "no_attribution_data" rather than inventing a value.

Usage:
    python3 attribution_estimate.py --signals signals.json
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Optional


def estimate_organic_installs(signals: dict[str, Any]) -> dict[str, Any]:
    """Triangulate a banded organic-install estimate from owned signals.

    signals (all real, owned counts the founder supplies/exports):
      landing_utm_installs, promo_code_redemptions, mmp_organic_bucket,
      brand_search_lift_installs, survey_tiktok_share (0-1), total_installs.
    """
    def num(key: str) -> float:
        v = signals.get(key)
        return float(v) if isinstance(v, (int, float)) else 0.0

    direct = num("landing_utm_installs") + num("promo_code_redemptions")
    lift = num("brand_search_lift_installs")

    survey = signals.get("survey_tiktok_share")
    total = signals.get("total_installs")
    survey_implied: Optional[float] = None
    if isinstance(survey, (int, float)) and isinstance(total, (int, float)) and total:
        survey_implied = survey * total

    mmp = signals.get("mmp_organic_bucket")
    mmp_v = float(mmp) if isinstance(mmp, (int, float)) else None

    # Each candidate is an independent triangulation method's point estimate.
    candidates: list[float] = []
    direct_plus_lift = direct + lift
    if direct_plus_lift > 0:
        candidates.append(direct_plus_lift)
    if mmp_v:
        candidates.append(mmp_v)
    if survey_implied:
        candidates.append(survey_implied)

    if not candidates:
        return {
            "value": None, "low": None, "high": None,
            "confidence": "NONE", "method": "insufficient_signals",
            "sources": [], "flags": ["no_attribution_data"],
        }

    low, high = min(candidates), max(candidates)
    point = round(sum(candidates) / len(candidates))

    # Wide bands (high > 2x low) ⇒ methods disagree ⇒ only LOW confidence.
    wide = bool(high and low and high > 2 * low)
    confidence = "LOW" if wide else "MEDIUM"

    flags = [
        "organic_attribution_is_approximate",
        "ddl_not_reliable_for_attribution",
    ]
    if len(candidates) == 1:
        flags.append("single_signal_only")
    if wide:
        flags.append("methods_disagree_wide_band")

    return {
        "value": point,
        "low": round(low),
        "high": round(high),
        "n_methods": len(candidates),
        "confidence": confidence,
        "method": "triangulated_estimate",
        "sources": ["owned_csv", "user_input"],
        "flags": flags,
    }


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Banded organic-install attribution estimator.")
    p.add_argument("--signals", required=True, help="Path to a JSON file of owned attribution signals")
    args = p.parse_args(argv)
    with open(args.signals, encoding="utf-8") as fh:
        signals = json.load(fh)
    print(json.dumps(estimate_organic_installs(signals), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
