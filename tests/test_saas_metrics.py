"""Stage 1 acceptance: saas_metrics.evaluate returns correct values and flags."""
import saas_metrics as m


BENCH = {"ltv_cac_floor": 3.0, "cac_payback_max_months": 12.0, "monthly_churn_warn": 0.03}


def test_pure_formulas():
    assert m.cac(1000, 50) == 20.0
    assert m.ltv(100, 0.8, 0.05) == 1600.0  # (100*0.8)/0.05
    assert m.ltv_cac(1600, 20) == 80.0
    assert m.cac_payback_months(240, 100, 0.8) == 3.0  # 240/(100*0.8)
    assert m.k_factor(5, 0.2) == 1.0


def test_zero_guards_return_none():
    assert m.cac(1000, 0) is None
    assert m.ltv(100, 0.8, 0) is None
    assert m.ltv_cac(1600, 0) is None
    assert m.cac_payback_months(240, 0, 0.8) is None


def test_annual_churn_compounding():
    # 1 - (1-0.05)^12 ~= 0.4596
    assert m.monthly_to_annual_churn(0.05) == 0.4596


def test_evaluate_healthy_no_flags():
    inputs = {
        "spend": 1000, "new_customers": 50,
        "arpa_monthly": 100, "arpu_monthly": 100,
        "gross_margin": 0.8, "monthly_churn": 0.02,
    }
    res = m.evaluate(inputs, BENCH)
    assert res["cac"] == 20.0
    assert res["ltv"] == 4000.0
    assert res["ltv_cac"] == 200.0
    assert res["confidence"] == "HIGH"
    assert res["method"] == "deterministic_formula"
    assert res["flags"] == []


def test_evaluate_fires_all_flags():
    inputs = {
        "spend": 5000, "new_customers": 50,   # CAC=100
        "arpa_monthly": 30, "arpu_monthly": 30,
        "gross_margin": 0.5, "monthly_churn": 0.10,  # high churn
    }
    res = m.evaluate(inputs, BENCH)
    # LTV = (30*0.5)/0.10 = 150 ; LTV:CAC = 1.5 < 3 floor
    assert "ltv_cac_below_floor" in res["flags"]
    # payback = 100/(30*0.5)=6.67 -> not too long... make sure churn flag fires
    assert "churn_above_warn" in res["flags"]


def test_evaluate_payback_too_long():
    inputs = {
        "spend": 10000, "new_customers": 50,  # CAC=200
        "arpa_monthly": 20, "arpu_monthly": 20,
        "gross_margin": 0.5, "monthly_churn": 0.01,
    }
    res = m.evaluate(inputs, BENCH)
    # payback = 200/(20*0.5)=20 > 12
    assert "payback_too_long" in res["flags"]


def test_missing_inputs_flagged():
    res = m.evaluate({"spend": 1000}, BENCH)
    assert any(f.startswith("missing_inputs:") for f in res["flags"])
