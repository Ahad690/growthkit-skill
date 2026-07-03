"""Tests for the append-only local observation store: every run stages
shareable rows, nothing is ever destroyed, and contribute.py reads the store
by default."""
import json
import os

import analyze_studio_csv as a
import fetch_trends as ft
import local_store

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "..", "examples", "sample_studio_export.csv")

ROW = {
    "platform": "tiktok", "data_type": "hashtag_trend", "industry": "saas",
    "country": "US", "metric_name": "publish_cnt:#saas", "metric_value": 1000,
    "period_days": 7, "captured_on": "2026-07-01", "source": "creative_center",
}


# --- append-only guarantees ----------------------------------------------
def test_append_and_dedup(tmp_path):
    store = str(tmp_path / "obs.json")
    r1 = local_store.append([ROW], path=store)
    assert r1["added"] == 1 and r1["total_staged"] == 1
    r2 = local_store.append([dict(ROW)], path=store)  # identical row
    assert r2["added"] == 0 and r2["skipped_duplicates"] == 1
    assert r2["total_staged"] == 1


def test_append_never_removes_existing_rows(tmp_path):
    store = str(tmp_path / "obs.json")
    local_store.append([ROW], path=store)
    new_row = dict(ROW, metric_name="video_views:#saas", metric_value=50000)
    local_store.append([new_row], path=store)
    staged = local_store.load(store)
    assert len(staged) == 2  # old row still there — nothing destroyed


def test_append_strips_to_shareable_schema(tmp_path):
    store = str(tmp_path / "obs.json")
    dirty = dict(ROW, handle="@founder", video_id="v123")  # must never be staged
    local_store.append([dirty], path=store)
    staged = local_store.load(store)
    assert "handle" not in staged[0] and "video_id" not in staged[0]


def test_corrupt_store_is_preserved_not_destroyed(tmp_path):
    store = str(tmp_path / "obs.json")
    with open(store, "w", encoding="utf-8") as fh:
        fh.write("{this is not json")
    local_store.append([ROW], path=store)
    # the corrupt bytes were moved aside, never deleted
    backups = [f for f in os.listdir(tmp_path) if ".corrupt-" in f]
    assert len(backups) == 1
    with open(os.path.join(tmp_path, backups[0]), encoding="utf-8") as fh:
        assert fh.read() == "{this is not json"
    assert len(local_store.load(store)) == 1  # fresh store carries on


# --- fetch_trends staging --------------------------------------------------
def _live_result():
    return {
        "items": [{"hashtag": "#saas", "rank": 1, "publish_cnt": 1000, "video_views": 50000}],
        "country": "US", "industry_id": "", "period_days": 7,
        "confidence": "MEDIUM", "method": "creative_center_live",
        "sources": ["creative_center"], "flags": ["external_best_effort"],
        "fetched_at": "2026-07-03T00:00:00Z",
    }


def test_observations_from_live_result():
    rows = ft.observations_from_result(_live_result())
    assert len(rows) == 2  # publish_cnt + video_views
    names = {r["metric_name"] for r in rows}
    assert names == {"publish_cnt:#saas", "video_views:#saas"}
    for r in rows:
        assert r["source"] == "creative_center"
        assert r["captured_on"] == "2026-07-03"
        assert r["industry"] == "all"  # empty industry_id -> non-empty label


def test_fallback_result_stages_nothing():
    fallback = ft.fetch_trending_hashtags(country="US")  # no headers -> fallback
    assert ft.observations_from_result(fallback) == []  # never re-stage stale data


def test_staged_fetch_rows_pass_contribution_schema():
    import validate as v
    for row in ft.observations_from_result(_live_result()):
        ok, reason = v.validate_row(row)
        assert ok, reason


# --- analyzer staging -------------------------------------------------------
def test_aggregate_benchmarks_medians_only():
    result = a.analyze(SAMPLE)
    rows = a.aggregate_benchmarks(result, "edtech", "US", captured_on="2026-07-03")
    names = {r["metric_name"] for r in rows}
    assert "completion_rate_median" in names
    # medians over the sample: completion rates .65,.05,.45,.08,.72 -> median .45
    med = next(r for r in rows if r["metric_name"] == "completion_rate_median")
    assert med["metric_value"] == 0.45
    for r in rows:
        assert r["source"] == "aggregated_owned"
        # NEVER per-post identifiers
        assert "video_id" not in r and "views" not in r


def test_aggregate_requires_min_posts():
    result = {"posts": [{"completion_rate": 0.5}, {"completion_rate": 0.6}]}  # only 2
    assert a.aggregate_benchmarks(result, "x", "US", min_posts=3) == []


def test_staged_analyzer_rows_pass_contribution_schema():
    import validate as v
    result = a.analyze(SAMPLE)
    for row in a.aggregate_benchmarks(result, "edtech", "US", captured_on="2026-07-03"):
        ok, reason = v.validate_row(row)
        assert ok, reason


# --- contribute reads the store by default ---------------------------------
def test_contribute_defaults_to_store(tmp_path, monkeypatch, capsys):
    import contribute as cb
    store = str(tmp_path / "obs.json")
    local_store.append([ROW], path=store)
    monkeypatch.setattr(local_store, "DEFAULT_STORE", store)
    rc = cb.main(["--dry-run"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["status"] == "dry_run_preview_only"
    assert out["n_shareable_rows"] == 1
    # contribution must NOT clear the store
    assert len(local_store.load(store)) == 1


def test_contribute_empty_store_is_honest(tmp_path, monkeypatch, capsys):
    import contribute as cb
    monkeypatch.setattr(local_store, "DEFAULT_STORE", str(tmp_path / "missing.json"))
    rc = cb.main(["--dry-run"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["status"] == "store_empty"
