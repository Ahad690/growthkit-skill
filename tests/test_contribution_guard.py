"""Stage 5 acceptance: assert_public_only raises on ANY banned field; dry-run
previews cleaned shareable rows; refresh refuses corrupt-heavy files and no-ops
below min_new."""
import os

import contribute as cb
import refresh_dataset as rd


# --- FR19: assert_public_only is the hard guard --------------------------
def test_assert_public_only_raises_on_handle():
    bad = [{"platform": "tiktok", "handle": "@founder", "metric_value": 1}]
    try:
        cb.assert_public_only(bad)
        assert False, "should have raised"
    except ValueError as e:
        assert "handle" in str(e)


def test_assert_public_only_raises_on_video_id_and_raw_csv():
    for field in ("video_id", "raw_csv", "profile_visits", "install_id", "email"):
        try:
            cb.assert_public_only([{field: "x"}])
            assert False, f"should have raised on {field}"
        except ValueError as e:
            assert field in str(e)


def test_build_contribution_strips_and_guards():
    rows = [{
        "platform": "tiktok", "data_type": "hashtag_trend", "industry": "saas",
        "country": "US", "metric_name": "publish_cnt", "metric_value": 1000,
        "period_days": 7, "captured_on": "2026-06-01", "source": "creative_center",
        # extraneous owned/identifying field that must be stripped (and is banned):
        "video_id": "should_never_appear",
    }]
    # build_contribution guards the ORIGINAL rows, so a banned field aborts.
    try:
        cb.build_contribution(rows)
        assert False, "banned field in input must abort"
    except ValueError as e:
        assert "video_id" in str(e)


def test_build_contribution_clean_rows_pass_and_dedup():
    row = {
        "platform": "tiktok", "data_type": "perf_benchmark", "industry": "saas",
        "country": "US", "metric_name": "completion_rate_median", "metric_value": 0.55,
        "period_days": 7, "captured_on": "2026-06-01", "source": "aggregated_owned",
    }
    cleaned = cb.build_contribution([row, dict(row)])  # duplicate
    assert len(cleaned) == 1
    assert set(cleaned[0].keys()) <= cb.SHAREABLE


def test_dry_run_previews_without_upload():
    row = {
        "platform": "tiktok", "data_type": "hashtag_trend", "industry": "saas",
        "country": "US", "metric_name": "publish_cnt", "metric_value": 1000,
        "period_days": 7, "captured_on": "2026-06-01", "source": "creative_center",
    }
    report = cb.contribute([row], dataset_id="Ahad690/growthkit-trends", dry_run=True)
    assert report["status"] == "dry_run_preview_only"
    assert report["will_upload"] is False
    assert report["shareable_rows"][0]["metric_name"] == "publish_cnt"


def test_no_token_means_no_upload(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    row = {
        "platform": "tiktok", "data_type": "hashtag_trend", "industry": "saas",
        "country": "US", "metric_name": "publish_cnt", "metric_value": 1000,
        "period_days": 7, "captured_on": "2026-06-01", "source": "creative_center",
    }
    report = cb.contribute([row], dataset_id="x/y", dry_run=False)
    assert report["status"] == "no_token_no_upload"
    assert report["will_upload"] is False


# --- FR20: refresh validation / corruption / min_new ---------------------
CONFIG = {"federation": {"min_new_on_refresh": 3, "max_corrupt_ratio": 0.25,
                         "dataset_id": "Ahad690/growthkit-trends"}}


def _good_row(i=0):
    return {
        "platform": "tiktok", "data_type": "perf_benchmark", "industry": "saas",
        "country": "US", "metric_name": "completion_rate", "metric_value": 0.5 + i * 0.01,
        "period_days": 7, "captured_on": "2026-06-01", "source": "aggregated_owned",
    }


def test_validate_row_rejects_banned_and_bad():
    assert rd.validate_row(_good_row()) is True
    bad = _good_row(); bad["handle"] = "@x"
    assert rd.validate_row(bad) is False
    neg = _good_row(); neg["metric_value"] = -1
    assert rd.validate_row(neg) is False
    missing = _good_row(); del missing["country"]
    assert rd.validate_row(missing) is False


def test_refresh_refuses_too_corrupt(tmp_path):
    import json as _json
    f = tmp_path / "rows.jsonl"
    # 3 corrupt lines + 1 clean => ratio 0.75 > 0.25
    f.write_text("garbage\n{bad\nnope\n" + _json.dumps(_good_row()) + "\n", encoding="utf-8")
    report = rd.refresh(config=CONFIG, local_path=str(f), dry_run=True)
    assert report["status"] == "refused_too_corrupt"


def test_refresh_noop_below_min_new(tmp_path):
    import json as _json
    f = tmp_path / "rows.jsonl"
    f.write_text(_json.dumps(_good_row()) + "\n", encoding="utf-8")  # 1 clean < min_new 3
    report = rd.refresh(config=CONFIG, local_path=str(f), dry_run=True)
    assert report["status"] == "noop_below_min_new"


def test_refresh_dry_run_previews_community_benchmarks(tmp_path):
    import json as _json
    f = tmp_path / "rows.jsonl"
    f.write_text("\n".join(_json.dumps(_good_row(i)) for i in range(5)) + "\n", encoding="utf-8")
    report = rd.refresh(config=CONFIG, local_path=str(f), dry_run=True)
    assert report["status"] == "dry_run_preview_only"
    assert report["n_clean"] == 5
    assert "saas|US" in report["preview_community_benchmarks"]
