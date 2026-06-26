"""Stage 2 acceptance (K3, hard gate): proves all four violation classes are
caught — non-CML business music, missing disclosure, restricted category, and
watermark re-upload."""
import json
import os

import compliance as c

HERE = os.path.dirname(os.path.abspath(__file__))
RESTRICTED = json.load(open(os.path.join(HERE, "..", "skills", "growthkit", "references", "restricted_categories.json"), encoding="utf-8"))


# --- FR14 music ----------------------------------------------------------
def test_non_cml_sound_on_business_account_caught():
    r = c.screen_music("business", {"source": "trending_commercial"})
    assert r["ok"] is False
    assert r["reason"] == "non_cml_sound_on_business_account"


def test_cml_and_original_sounds_allowed_on_business():
    assert c.screen_music("business", {"source": "cml"})["ok"] is True
    assert c.screen_music("business", {"source": "original"})["ok"] is True
    assert c.screen_music("business", {"source": "owned"})["ok"] is True


def test_personal_account_can_use_trending_sound():
    assert c.screen_music("personal", {"source": "trending_commercial"})["ok"] is True


# --- FR15 disclosure -----------------------------------------------------
def test_missing_disclosure_caught():
    r = c.screen_disclosure("Buy our app now! #ad")
    assert r["ok"] is False
    assert r["reason"] == "missing_disclosure_block"


def test_disclosure_present_passes():
    text = "Check out our app.\n\n" + c.disclosure_block()
    assert c.screen_disclosure(text)["ok"] is True


# --- FR16 restricted category -------------------------------------------
def test_restricted_category_caught():
    r = c.screen_category("crypto", RESTRICTED)
    assert r["ok"] is False
    assert r["reason"] == "restricted_or_approval_gated"
    assert "detail" in r


def test_unrestricted_category_passes():
    assert c.screen_category("productivity_app", RESTRICTED)["ok"] is True
    assert c.screen_category(None, RESTRICTED)["ok"] is True


# --- FR17 repurposing watermark -----------------------------------------
def test_watermark_reupload_advice_caught():
    bad = "Just download the TikTok video with the watermark and re-upload it to Reels."
    r = c.screen_repurposing(bad)
    assert r["ok"] is False
    assert r["reason"] == "watermark_reupload_advice"


def test_clean_master_advice_passes():
    good = "Repurpose to Reels. " + c.REPURPOSE_RULE
    assert c.screen_repurposing(good)["ok"] is True


# --- Aggregate gate: all four at once -----------------------------------
def test_aggregate_gate_catches_all_four_violations():
    res = c.gate_promotional_output(
        account_type="business",
        is_promotional=True,
        sound={"source": "trending_commercial"},
        category="crypto",
        restricted=RESTRICTED,
        output_text="Buy now!",  # no disclosure block
        repurposing_text="download the TikTok with the watermark and re-upload",
    )
    assert res["ok"] is False
    guards = {v["guard"] for v in res["violations"]}
    assert {"music", "disclosure", "category", "repurposing"} <= guards


def test_aggregate_gate_passes_when_compliant():
    text = "Educational tip about our tool.\n\n" + c.disclosure_block()
    res = c.gate_promotional_output(
        account_type="business",
        is_promotional=True,
        sound={"source": "cml"},
        category="productivity_app",
        restricted=RESTRICTED,
        output_text=text,
        repurposing_text="Export a clean master. " + c.REPURPOSE_RULE,
    )
    assert res["ok"] is True
    assert res["violations"] == []
