"""Stage 1 acceptance (K5): analyzer metrics match hand calculations and
hook_failure fires below the 3-sec-view floor."""
import os

import analyze_studio_csv as a

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "..", "examples", "sample_studio_export.csv")


def _by_id(result):
    return {p["video_id"]: p for p in result["posts"]}


def test_completion_and_watch_match_hand_calc():
    res = a.analyze(SAMPLE, three_sec_floor=0.20)
    posts = _by_id(res)

    # v001: dur=30, awt=24 -> watch_pct=0.8 ; completion=65% -> 0.65
    assert posts["v001"]["watch_time_pct"] == 0.8
    assert posts["v001"]["completion_rate"] == 0.65
    # share_rate = 200/10000 = 0.02 ; save_rate = 300/10000 = 0.03
    assert posts["v001"]["share_rate"] == 0.02
    assert posts["v001"]["save_rate"] == 0.03
    # profile_visit_rate = 500/10000 = 0.05
    assert posts["v001"]["profile_visit_rate"] == 0.05

    # v005: dur=10, awt=8 -> 0.8 ; completion 72% -> 0.72 ; share 1500/50000 = 0.03
    assert posts["v005"]["completion_rate"] == 0.72
    assert posts["v005"]["share_rate"] == 0.03


def test_hook_failure_fires_below_floor():
    res = a.analyze(SAMPLE, three_sec_floor=0.20)
    posts = _by_id(res)
    # v002 watch_pct = 2/20 = 0.1 < 0.20 -> hook_failure
    assert "hook_failure" in posts["v002"]["flags"]
    # v004 watch_pct = 4.5/45 = 0.1 < 0.20 -> hook_failure
    assert "hook_failure" in posts["v004"]["flags"]
    # v001 watch_pct = 0.8 -> NOT a hook failure
    assert "hook_failure" not in posts["v001"]["flags"]
    assert res["n_hook_failures"] == 2


def test_winners_sorted_by_completion():
    res = a.analyze(SAMPLE, three_sec_floor=0.20, top_n=3)
    ids = [w["video_id"] for w in res["top_by_completion"]]
    assert ids[:3] == ["v005", "v001", "v003"]


def test_provenance_is_owned_and_high():
    res = a.analyze(SAMPLE)
    assert res["method"] == "owned_studio_csv"
    assert res["sources"] == ["owned_csv"]
    assert res["confidence"] == "HIGH"
    for p in res["posts"]:
        assert p["sources"] == ["owned_csv"]


def test_missing_file_does_not_crash():
    res = a.analyze("does_not_exist_12345.csv")
    assert res["confidence"] == "NONE"
    assert "missing_data" in res["flags"]
    assert res["posts"] == []


def test_column_alias_tolerance(tmp_path):
    # Use variant headers ("Completion Rate", "Average Watch Time", "Plays")
    p = tmp_path / "variant.csv"
    p.write_text(
        "id,date,Plays,Duration,Average Watch Time,Completion Rate,Shares,Saves\n"
        "x1,2026-01-01,1000,20,16,0.5,10,20\n",
        encoding="utf-8",
    )
    res = a.analyze(str(p))
    post = res["posts"][0]
    assert post["video_id"] == "x1"
    assert post["watch_time_pct"] == 0.8  # 16/20
    assert post["completion_rate"] == 0.5
    assert post["share_rate"] == 0.01  # 10/1000
