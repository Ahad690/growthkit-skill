"""Stage 1 acceptance: attribution returns a BAND (not a scalar) and NONE +
no_attribution_data when given no signals."""
import attribution_estimate as att


def test_no_signals_returns_none_not_fabricated():
    res = att.estimate_organic_installs({})
    assert res["value"] is None
    assert res["confidence"] == "NONE"
    assert "no_attribution_data" in res["flags"]


def test_returns_band_with_low_high():
    signals = {
        "landing_utm_installs": 100,
        "promo_code_redemptions": 50,      # direct = 150
        "brand_search_lift_installs": 50,  # direct+lift = 200
        "mmp_organic_bucket": 400,
        "survey_tiktok_share": 0.3,
        "total_installs": 1000,            # survey_implied = 300
    }
    res = att.estimate_organic_installs(signals)
    # candidates: 200, 400, 300 -> low=200, high=400, point=300
    assert res["low"] == 200
    assert res["high"] == 400
    assert res["value"] == 300
    assert res["low"] != res["high"]  # it's a band, never a bare scalar
    assert "low" in res and "high" in res
    assert "organic_attribution_is_approximate" in res["flags"]
    assert "ddl_not_reliable_for_attribution" in res["flags"]


def test_estimate_never_high_confidence():
    signals = {"landing_utm_installs": 100, "mmp_organic_bucket": 110}
    res = att.estimate_organic_installs(signals)
    assert res["confidence"] in ("LOW", "MEDIUM")  # estimates cap at MEDIUM
    assert res["confidence"] != "HIGH"


def test_wide_band_is_low_confidence():
    signals = {"landing_utm_installs": 100, "mmp_organic_bucket": 1000}  # high > 2*low
    res = att.estimate_organic_installs(signals)
    assert res["confidence"] == "LOW"
    assert "methods_disagree_wide_band" in res["flags"]


def test_single_signal_flagged():
    res = att.estimate_organic_installs({"mmp_organic_bucket": 250})
    assert res["value"] == 250
    assert "single_signal_only" in res["flags"]
