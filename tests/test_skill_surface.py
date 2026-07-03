"""Tests for the conversation-first skill surface: direct CLI flags on the
deterministic scripts (no hand-authored input files) and the growth-plan.html
deliverable renderer (presentation-only, disclosure stamped in depth)."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "skills", "growthkit", "scripts")


def run_script(name, *args):
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, name), *args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


# --- direct CLI flags -----------------------------------------------------
def test_saas_metrics_direct_flags():
    code, out, _ = run_script(
        "saas_metrics.py", "--spend", "1000", "--new-customers", "50",
        "--arpa-monthly", "100", "--arpu-monthly", "100",
        "--gross-margin", "0.8", "--monthly-churn", "0.02")
    assert code == 0
    d = json.loads(out)
    assert d["cac"] == 20.0 and d["ltv"] == 4000.0
    assert d["method"] == "deterministic_formula"


def test_saas_metrics_requires_some_input():
    code, _, err = run_script("saas_metrics.py")
    assert code != 0
    assert "provide --inputs" in err


def test_funnel_stage_flags_preserve_order():
    code, out, _ = run_script(
        "funnel_diagnose.py", "--stage", "visitors=10000",
        "--stage", "signups=1200", "--stage", "paid=60")
    assert code == 0
    d = json.loads(out)
    assert [s["from"] for s in d["steps"]] == ["visitors", "signups"]
    assert d["biggest_bottleneck"]["from"] == "signups"


def test_funnel_rejects_malformed_stage():
    code, _, err = run_script("funnel_diagnose.py", "--stage", "nonsense")
    assert code != 0
    assert "NAME=COUNT" in err


def test_attribution_direct_flags_return_band():
    code, out, _ = run_script(
        "attribution_estimate.py", "--landing-utm-installs", "100",
        "--promo-code-redemptions", "50", "--mmp-organic-bucket", "400",
        "--survey-tiktok-share", "0.3", "--total-installs", "1000")
    assert code == 0
    d = json.loads(out)
    assert d["low"] == 150 and d["high"] == 400
    assert d["confidence"] in ("LOW", "MEDIUM")


def test_attribution_no_flags_is_honest_none():
    code, out, _ = run_script("attribution_estimate.py")
    assert code == 0
    d = json.loads(out)
    assert d["confidence"] == "NONE"
    assert "no_attribution_data" in d["flags"]


# --- deliverable renderer ---------------------------------------------------
PLAN = {
    "product": {"name": "TestApp", "variant": "B2C-install × TikTok-native",
                "why_variant": "US market, TikTok available"},
    "positioning": {"statement": "For X who Y, TestApp does Z."},
    "pillars": {"educational": 0.6, "entertainment": 0.3, "promotional": 0.1},
    "calendar": [{"week": 1, "posts": [
        {"day": "Mon", "pillar": "educational", "hook": "H", "value": "V",
         "cta": "C", "hashtags": ["#a", "#b", "#c"], "promotional": False},
        # promo post deliberately WITHOUT a disclosure field:
        {"day": "Fri", "pillar": "promotional", "hook": "Buy", "value": "Demo",
         "cta": "Install", "promotional": True},
    ]}],
    "metrics": [
        {"label": "CAC", "value": 20.0, "unit": "$", "confidence": "HIGH",
         "method": "deterministic_formula", "sources": ["user_input"], "flags": []},
        {"label": "Organic installs", "value": 283, "low": 150, "high": 400,
         "confidence": "LOW", "method": "triangulated_estimate",
         "sources": ["owned_csv"], "flags": ["organic_attribution_is_approximate"]},
    ],
    "compliance": {"account_type": "business", "category": "productivity_app"},
}


def _render(tmp_path, plan=None):
    plan_path = tmp_path / "plan.json"
    out_path = tmp_path / "plan.html"
    plan_path.write_text(json.dumps(plan or PLAN), encoding="utf-8")
    code, out, err = run_script("build_plan.py", str(plan_path), "--out", str(out_path))
    assert code == 0, err
    return out_path.read_text(encoding="utf-8"), json.loads(out)


def test_renderer_writes_deliverable(tmp_path):
    html, report = _render(tmp_path)
    assert report["posts"] == 2 and report["metrics"] == 2
    assert "TestApp" in html


def test_renderer_stamps_disclosure_on_undisclosed_promo(tmp_path):
    html, _ = _render(tmp_path)
    # The promo post had NO disclosure field — the renderer must stamp the block.
    assert "Commercial Content Disclosure toggle" in html
    assert "bio disclosure does NOT cover" in html


def test_renderer_shows_provenance_and_bands(tmp_path):
    html, _ = _render(tmp_path)
    assert "triangulated_estimate" in html
    assert "band" in html  # 150–400 rendered as a band, not a bare scalar
    assert "deterministic_formula" in html


def test_renderer_carries_contribution_banner_and_repurpose_rule(tmp_path):
    html, _ = _render(tmp_path)
    assert "contribute your anonymized data" in html
    assert "CLEAN master" in html


def test_renderer_escapes_html_in_user_content(tmp_path):
    plan = json.loads(json.dumps(PLAN))
    plan["product"]["name"] = "<script>alert(1)</script>"
    html, _ = _render(tmp_path, plan)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
