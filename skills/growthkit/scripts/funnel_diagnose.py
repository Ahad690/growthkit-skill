#!/usr/bin/env python3
"""funnel_diagnose.py — AARRR / RARRA funnel diagnostic (FR5).

The founder inputs stage counts; this script deterministically computes
stage-to-stage conversion, drop-offs, and names the biggest bottleneck. No
benchmarks are invented — it reports the founder's own numbers and where the
largest relative leak is.

HONESTY (P1/P3): deterministic over user-supplied counts.
confidence="HIGH", method="deterministic_funnel", sources=["user_input"].

Usage:
    python3 funnel_diagnose.py --stages stages.json
where stages.json is an ORDERED object, e.g.:
    {"visitors": 10000, "signups": 1200, "activated": 400, "paid": 60, "retained_d30": 30}
or AARRR named stages. Order is preserved (Python 3.7+ dict order).
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Optional


def diagnose(stages: dict[str, float]) -> dict[str, Any]:
    """Compute step conversions and identify the biggest bottleneck."""
    names = list(stages.keys())
    if len(names) < 2:
        return {
            "steps": [], "biggest_bottleneck": None,
            "confidence": "NONE", "method": "deterministic_funnel",
            "sources": ["user_input"], "flags": ["need_at_least_two_stages"],
        }

    steps: list[dict[str, Any]] = []
    for i in range(1, len(names)):
        prev_name, cur_name = names[i - 1], names[i]
        prev_v = stages[prev_name]
        cur_v = stages[cur_name]
        conv = (cur_v / prev_v) if prev_v else None
        drop = (1 - conv) if conv is not None else None
        steps.append({
            "from": prev_name,
            "to": cur_name,
            "from_count": prev_v,
            "to_count": cur_v,
            "conversion": round(conv, 4) if conv is not None else None,
            "drop_off": round(drop, 4) if drop is not None else None,
        })

    # Biggest bottleneck = step with the largest drop-off (lowest conversion).
    valid = [s for s in steps if s["drop_off"] is not None]
    bottleneck = max(valid, key=lambda s: s["drop_off"]) if valid else None

    flags: list[str] = []
    if any(s["conversion"] is None for s in steps):
        flags.append("some_stages_zero_or_missing")

    return {
        "steps": steps,
        "biggest_bottleneck": (
            {"from": bottleneck["from"], "to": bottleneck["to"],
             "drop_off": bottleneck["drop_off"], "conversion": bottleneck["conversion"]}
            if bottleneck else None
        ),
        "confidence": "HIGH",
        "method": "deterministic_funnel",
        "sources": ["user_input"],
        "flags": flags,
    }


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="AARRR/RARRA funnel diagnostic.")
    p.add_argument("--stages", required=True, help="Path to an ordered JSON object of stage counts")
    args = p.parse_args(argv)
    with open(args.stages, encoding="utf-8") as fh:
        stages = json.load(fh)
    print(json.dumps(diagnose(stages), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
