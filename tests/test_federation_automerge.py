"""Tests for the HF auto-merge pattern alignment: validate.py guard stack,
automerge additive-only + verdict logic, content-addressed contribution paths,
and the contribution-nudge notifications module. No network required."""
import automerge
import contribute as cb
import notifications
import validate as v


GOOD = {
    "platform": "tiktok", "data_type": "hashtag_trend", "industry": "saas",
    "country": "US", "metric_name": "publish_cnt", "metric_value": 1000,
    "period_days": 7, "captured_on": "2026-06-01", "source": "creative_center",
}


# --- validate.py: schema / PII / range / enum ---------------------------
def test_validate_good_row():
    assert v.validate_row(GOOD)[0] is True


def test_validate_rejects_pii_range_enum():
    assert v.validate_row(dict(GOOD, handle="@x"))[0] is False          # PII
    assert v.validate_row(dict(GOOD, metric_value=-1))[0] is False       # range
    assert v.validate_row(dict(GOOD, data_type="nope"))[0] is False      # enum
    assert v.validate_row(dict(GOOD, period_days=9999))[0] is False      # range max
    bad = dict(GOOD); del bad["country"]
    assert v.validate_row(bad)[0] is False                               # required


def test_strip_to_keep_drops_stray_fields():
    stripped = v.strip_to_keep(dict(GOOD, secret="x", handle="@y"), v.SHAREABLE)
    assert set(stripped.keys()) <= set(v.SHAREABLE)
    assert "secret" not in stripped and "handle" not in stripped


def test_decide_corrupt_ratio_zero_holds_on_any_invalid():
    assert v.decide(10, 0, 8, 1, 0.0, 0)["action"] == "merge"
    assert v.decide(10, 1, 9, 1, 0.0, 0)["action"] == "abort"
    assert v.decide(0, 0, 0, 1, 0.0, 0)["action"] == "noop"
    assert v.decide(10, 0, 0, 5, 0.0, 0)["action"] == "noop"  # below min_new


# --- abuse heuristics ----------------------------------------------------
def test_abuse_flags_duplicate_flooding():
    rows = [dict(GOOD) for _ in range(10)]  # all identical
    reasons = v.abuse_scan(rows, [], v.GROWTHKIT_ABUSE)
    assert any("unique" in r for r in reasons)


def test_abuse_flags_group_median_outlier():
    ref = [dict(GOOD, metric_name="completion_rate", metric_value=0.5) for _ in range(5)]
    cur = [dict(GOOD, metric_name="completion_rate", metric_value=300) for _ in range(5)]
    reasons = v.abuse_scan(cur, ref, v.GROWTHKIT_ABUSE)
    assert any("outlier" in r for r in reasons)


def test_abuse_clean_when_reasonable():
    rows = [dict(GOOD, country=c) for c in ("US", "GB", "CA", "DE", "FR", "BR")]
    assert v.abuse_scan(rows, [], v.GROWTHKIT_ABUSE) == []


# --- automerge: additive-only + verdict ----------------------------------
def test_additive_only_rejects_removes_modifies_and_foreign_files():
    cfg = automerge.CONFIG
    assert automerge.additive_only(["contributions/a-1.json"], [], [], cfg)[0] is True
    assert automerge.additive_only(["contributions/a-1.json"], ["x"], [], cfg)[0] is False
    assert automerge.additive_only(["contributions/a-1.json"], [], ["README.md"], cfg)[0] is False
    assert automerge.additive_only(["README.md"], [], [], cfg)[0] is False  # foreign file
    assert automerge.additive_only([], [], [], cfg)[0] is False             # nothing added


def test_pr_verdict_merges_clean_additive_pr():
    cfg = automerge.CONFIG
    verdict = automerge.pr_verdict(
        added=["contributions/ahad-abc123.json"], removed=[], modified=[],
        rows=1, invalid=0, valid_new=1, errs=0, cfg=cfg, abuse_reasons=[],
    )
    assert verdict["action"] == "merge"


def test_pr_verdict_holds_on_invalid_row():
    cfg = automerge.CONFIG
    verdict = automerge.pr_verdict(
        added=["contributions/ahad-abc123.json"], removed=[], modified=[],
        rows=2, invalid=1, valid_new=1, errs=0, cfg=cfg, abuse_reasons=[],
    )
    assert verdict["action"] == "hold"
    assert verdict["status"] == "corrupt"


def test_pr_verdict_holds_on_suspicious():
    cfg = automerge.CONFIG
    verdict = automerge.pr_verdict(
        added=["contributions/ahad-abc123.json"], removed=[], modified=[],
        rows=1, invalid=0, valid_new=1, errs=0, cfg=cfg,
        abuse_reasons=["only 1/10 unique rows (flooding)"],
    )
    assert verdict["action"] == "hold"
    assert verdict["status"] == "suspicious"


# --- contribute: content-addressed, append-only paths --------------------
def test_contribution_path_is_content_addressed_and_idempotent():
    p1 = cb.contribution_path([GOOD], "Ahad690")
    p2 = cb.contribution_path([GOOD], "Ahad690")
    assert p1 == p2  # idempotent: same payload => same filename
    assert p1.startswith("contributions/Ahad690-") and p1.endswith(".json")


def test_contribution_path_differs_by_payload():
    p1 = cb.contribution_path([GOOD], "Ahad690")
    p2 = cb.contribution_path([dict(GOOD, country="GB")], "Ahad690")
    assert p1 != p2


def test_contribution_path_sanitizes_author():
    p = cb.contribution_path([GOOD], "../../etc/passwd")
    assert ".." not in p
    assert p.startswith("contributions/")
    assert p.count("/") == 1  # only the contributions/ separator, no path traversal


# --- notifications: config-gated nudge -----------------------------------
def test_nudge_on_by_default():
    line = notifications.contribution_line_text({"federation": {"dataset_repo": "https://hf.co/x"}})
    assert "contribute" in line.lower()
    assert "https://hf.co/x" in line


def test_nudge_off_when_flag_false():
    cfg = {"ui": {"contribution_reminder": False}}
    assert notifications.contribution_line_text(cfg) == ""
    assert notifications.contribution_banner_html(cfg) == ""


def test_nudge_html_escapes_repo():
    cfg = {"federation": {"dataset_repo": "https://hf.co/x?a=1&b=2"}}
    banner = notifications.contribution_banner_html(cfg)
    assert "&amp;" in banner  # & escaped
