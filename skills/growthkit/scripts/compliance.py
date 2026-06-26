#!/usr/bin/env python3
"""compliance.py — compliance HARD GATE (FR14-FR17, §9E, P5).

Wraps ALL promotional output. Enforces, with no override path in normal use:
  - FR14 Music guard: business accounts → Commercial Music Library (CML) or
    original/owned audio ONLY. Never reuse a trending non-CML sound.
  - FR15 Disclosure guard: any promotional/branded script gets the mandatory
    in-app Commercial Content Disclosure toggle + first-line + verbal +
    on-screen disclosure guidance. A bio disclosure does NOT cover a post.
  - FR16 Restricted-category check: screen the product category against
    restricted_categories.json before generating a campaign.
  - FR17 Repurposing guard: always export a CLEAN master; never download the
    watermarked TikTok and re-upload (cross-platform watermark down-rank).

These are HARD requirements (K3 = 0 violations). The model must call
gate_promotional_output() and refuse to emit anything it returns as not ok.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Optional

CML_OK_SOURCES = ("cml", "commercial_music_library", "original", "owned")


# ---------------------------------------------------------------------------
# FR14 — Music guard
# ---------------------------------------------------------------------------
def screen_music(account_type: str, sound: dict[str, Any]) -> dict[str, Any]:
    """Business accounts: CML or original/owned audio only."""
    source = (sound or {}).get("source")
    norm = str(source).lower() if source is not None else None
    if account_type == "business" and norm not in CML_OK_SOURCES:
        return {
            "ok": False,
            "reason": "non_cml_sound_on_business_account",
            "fix": "Use a Commercial Music Library track or your own/original audio. "
                   "Business accounts cannot legally use most trending commercial sounds.",
        }
    return {"ok": True}


# ---------------------------------------------------------------------------
# FR15 — Disclosure guard
# ---------------------------------------------------------------------------
def disclosure_block() -> str:
    return (
        "Enable TikTok's Commercial Content Disclosure toggle (select 'Your brand' / "
        "'Promotional content'). Add a first-line caption disclosure, say it in the first "
        "~3 seconds, and put it as on-screen text. A bio disclosure does NOT cover "
        "individual posts."
    )


def screen_disclosure(text: Optional[str]) -> dict[str, Any]:
    """Return ok only if the disclosure block is present in promotional output."""
    if not text or disclosure_block() not in text:
        return {
            "ok": False,
            "reason": "missing_disclosure_block",
            "fix": disclosure_block(),
        }
    return {"ok": True}


# ---------------------------------------------------------------------------
# FR16 — Restricted-category check
# ---------------------------------------------------------------------------
def screen_category(category: Optional[str], restricted: dict[str, Any]) -> dict[str, Any]:
    """Screen the product category against the restricted-categories map.

    `restricted` may be the full restricted_categories.json (with a 'categories'
    key) or the inner mapping directly.
    """
    if not category:
        return {"ok": True}
    table = restricted.get("categories", restricted) if isinstance(restricted, dict) else {}
    hit = table.get(category) or table.get(str(category).lower())
    if hit:
        return {
            "ok": False,
            "reason": "restricted_or_approval_gated",
            "detail": hit,
        }
    return {"ok": True}


# ---------------------------------------------------------------------------
# FR17 — Repurposing guard
# ---------------------------------------------------------------------------
REPURPOSE_RULE = (
    "Export a CLEAN master before posting; never download the watermarked TikTok and "
    "re-upload it (Reels/Shorts down-rank other-platform watermarks). Re-upload natively, "
    "and note CML clearance is TikTok-only — cross-platform reuse needs a separate license."
)


def screen_repurposing(plan_text: Optional[str]) -> dict[str, Any]:
    """Catch advice to re-upload a watermarked download."""
    if not plan_text:
        return {"ok": True}
    low = plan_text.lower()
    watermark_mentions = "watermark" in low or "save the tiktok" in low or "download the tiktok" in low
    bad_pattern = (
        ("download" in low or "save" in low or "re-upload" in low or "reupload" in low)
        and ("watermark" in low or "tiktok video" in low or "the tiktok" in low)
        and REPURPOSE_RULE not in plan_text
    )
    if bad_pattern:
        return {
            "ok": False,
            "reason": "watermark_reupload_advice",
            "fix": REPURPOSE_RULE,
        }
    return {"ok": True}


# ---------------------------------------------------------------------------
# Aggregate gate — call this before showing ANY promotional output.
# ---------------------------------------------------------------------------
def gate_promotional_output(
    *,
    account_type: str = "business",
    is_promotional: bool = True,
    sound: Optional[dict[str, Any]] = None,
    category: Optional[str] = None,
    restricted: Optional[dict[str, Any]] = None,
    output_text: Optional[str] = None,
    repurposing_text: Optional[str] = None,
) -> dict[str, Any]:
    """Run all applicable guards. Returns {ok, violations:[...], required_block?}."""
    violations: list[dict[str, Any]] = []

    if sound is not None:
        r = screen_music(account_type, sound)
        if not r["ok"]:
            violations.append({"guard": "music", **r})

    if category is not None and restricted is not None:
        r = screen_category(category, restricted)
        if not r["ok"]:
            violations.append({"guard": "category", **r})

    if is_promotional:
        r = screen_disclosure(output_text)
        if not r["ok"]:
            violations.append({"guard": "disclosure", **r})

    if repurposing_text is not None:
        r = screen_repurposing(repurposing_text)
        if not r["ok"]:
            violations.append({"guard": "repurposing", **r})

    return {
        "ok": len(violations) == 0,
        "violations": violations,
        "required_disclosure_block": disclosure_block() if is_promotional else None,
        "repurpose_rule": REPURPOSE_RULE,
    }


def _load_restricted() -> dict[str, Any]:
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "references", "restricted_categories.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Compliance hard-gate screener.")
    p.add_argument("--account-type", default="business")
    p.add_argument("--category", default=None)
    p.add_argument("--sound-source", default=None, help="e.g. cml | original | owned | trending")
    p.add_argument("--check-category", action="store_true", help="Only run the category screen")
    args = p.parse_args(argv)

    restricted = _load_restricted()
    sound = {"source": args.sound_source} if args.sound_source else None
    result = gate_promotional_output(
        account_type=args.account_type,
        is_promotional=False,
        sound=sound,
        category=args.category,
        restricted=restricted,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
