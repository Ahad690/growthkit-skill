#!/usr/bin/env python3
"""saas_metrics.py — deterministic SaaS metrics calculator (FR12, §9C).

Computes CAC, LTV (gross-margin formula), LTV:CAC, CAC payback, churn→annual,
and K-factor from RAW inputs the founder supplies. Flags results against the
thresholds in benchmarks.json / config.json.

HONESTY (P1/P3): these are deterministic formulas over user-supplied numbers.
Provenance: confidence="HIGH" (a direct computation of supplied facts),
method="deterministic_formula", sources=["user_input"]. The model never emits
these numbers — this script does.

Usage:
    python3 saas_metrics.py --inputs inputs.json [--benchmarks benchmarks.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Optional

DEFAULT_BENCHMARKS: dict[str, float] = {
    "ltv_cac_floor": 3.0,
    "cac_payback_max_months": 12.0,
    "monthly_churn_warn": 0.03,
}


def cac(spend: Optional[float], new_customers: Optional[float]) -> Optional[float]:
    return spend / new_customers if (spend is not None and new_customers) else None


def ltv(arpa_monthly: Optional[float], gross_margin: Optional[float], monthly_churn: Optional[float]) -> Optional[float]:
    """LTV = (ARPA * gross_margin) / monthly_churn. None if churn is 0/missing."""
    if not monthly_churn or arpa_monthly is None or gross_margin is None:
        return None
    return (arpa_monthly * gross_margin) / monthly_churn


def ltv_cac(ltv_v: Optional[float], cac_v: Optional[float]) -> Optional[float]:
    return (ltv_v / cac_v) if (ltv_v is not None and cac_v) else None


def cac_payback_months(cac_v: Optional[float], arpu_monthly: Optional[float], gross_margin: Optional[float]) -> Optional[float]:
    if cac_v is None or arpu_monthly is None or gross_margin is None:
        return None
    d = arpu_monthly * gross_margin
    return (cac_v / d) if d else None


def k_factor(invites_per_user: Optional[float], conversion_rate: Optional[float]) -> Optional[float]:
    if invites_per_user is None or conversion_rate is None:
        return None
    return invites_per_user * conversion_rate


def monthly_to_annual_churn(monthly_churn: Optional[float]) -> Optional[float]:
    """Compound monthly churn to an annual figure: 1 - (1 - m)^12."""
    if monthly_churn is None:
        return None
    return round(1 - (1 - monthly_churn) ** 12, 4)


def evaluate(inputs: dict[str, Any], benchmarks: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Evaluate the full metric set with threshold flags. Tolerant of missing inputs."""
    bm = {**DEFAULT_BENCHMARKS, **(benchmarks or {})}

    c = cac(inputs.get("spend"), inputs.get("new_customers"))
    l = ltv(inputs.get("arpa_monthly"), inputs.get("gross_margin"), inputs.get("monthly_churn"))
    ratio = ltv_cac(l, c)
    payback = cac_payback_months(c, inputs.get("arpu_monthly"), inputs.get("gross_margin"))
    annual_churn = monthly_to_annual_churn(inputs.get("monthly_churn"))
    kf = k_factor(inputs.get("invites_per_user"), inputs.get("invite_conversion_rate"))

    flags: list[str] = []
    if ratio is not None and ratio < bm["ltv_cac_floor"]:
        flags.append("ltv_cac_below_floor")
    if payback is not None and payback > bm["cac_payback_max_months"]:
        flags.append("payback_too_long")
    if inputs.get("monthly_churn") is not None and inputs["monthly_churn"] > bm["monthly_churn_warn"]:
        flags.append("churn_above_warn")

    missing = [k for k in ("spend", "new_customers", "arpa_monthly", "gross_margin", "monthly_churn")
               if inputs.get(k) is None]
    if missing:
        flags.append("missing_inputs:" + ",".join(missing))

    return {
        "cac": _r(c),
        "ltv": _r(l),
        "ltv_cac": _r(ratio),
        "cac_payback_months": _r(payback),
        "annual_churn": annual_churn,
        "k_factor": _r(kf),
        "confidence": "HIGH",
        "method": "deterministic_formula",
        "sources": ["user_input"],
        "flags": flags,
    }


def _r(x: Optional[float]) -> Optional[float]:
    return round(x, 4) if x is not None else None


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Deterministic SaaS metrics calculator.")
    p.add_argument("--inputs", required=True, help="Path to a JSON file of raw inputs")
    p.add_argument("--benchmarks", help="Optional path to a benchmarks JSON (config.saas_benchmarks shape)")
    args = p.parse_args(argv)

    with open(args.inputs, encoding="utf-8") as fh:
        inputs = json.load(fh)

    bm = None
    if args.benchmarks and os.path.exists(args.benchmarks):
        with open(args.benchmarks, encoding="utf-8") as fh:
            raw = json.load(fh)
        bm = raw.get("saas_benchmarks", raw)

    print(json.dumps(evaluate(inputs, bm), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
