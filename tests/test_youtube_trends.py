"""YouTube trend collector: real aggregates only, and silence on failure.

The point of this collector is that it rests on an official API, so these tests
pin the honesty contract rather than the network: nothing is ever staged unless a
real fetch succeeded, and only aggregate rows (never a per-video field the
federation guard bans) can leave the machine.
"""
from unittest import mock

import fetch_youtube_trends as yt
from federation.validate import BANNED, SHAREABLE


def _item(views, likes=None, comments=None, duration="PT45S"):
    st = {"viewCount": str(views)}
    if likes is not None:
        st["likeCount"] = str(likes)
    if comments is not None:
        st["commentCount"] = str(comments)
    return {"statistics": st, "contentDetails": {"duration": duration}}


class _Resp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status

    def json(self):
        return self._p


def test_parse_iso_duration():
    assert yt.parse_iso_duration("PT45S") == 45
    assert yt.parse_iso_duration("PT1M30S") == 90
    assert yt.parse_iso_duration("PT2H1M") == 7260
    assert yt.parse_iso_duration("garbage") is None
    assert yt.parse_iso_duration(None) is None


def test_summarize_medians_rates_per_video_not_ratio_of_sums():
    # One mega-viral video with a poor rate must not drag the benchmark: the
    # median of per-video rates ignores its magnitude.
    items = [_item(100, 10, 1), _item(200, 20, 2), _item(10_000_000, 1000, 100)]
    s = yt.summarize(items)
    assert s["sample_size"] == 3
    assert s["view_count_median"] == 200
    assert abs(s["like_rate_median"] - 0.10) < 1e-9
    assert abs(s["comment_rate_median"] - 0.01) < 1e-9
    assert abs(s["engagement_rate_median"] - 0.11) < 1e-9


def test_summarize_skips_hidden_counts_instead_of_zero_filling():
    # Uploaders can hide likes/comments. Treating absent as 0 would silently
    # depress the benchmark, so those videos contribute views only.
    s = yt.summarize([_item(100, 10, 1), _item(500)])
    assert s["sample_size"] == 2
    assert abs(s["like_rate_median"] - 0.10) < 1e-9  # from the one that has it


def test_short_form_shares():
    s = yt.summarize([_item(10, duration="PT30S"), _item(10, duration="PT2M"),
                      _item(10, duration="PT10M"), _item(10, duration="PT45S")])
    assert abs(s["short_form_share"] - 0.75) < 1e-9   # <=180s
    assert abs(s["sub_60s_share"] - 0.50) < 1e-9      # <=60s


def test_no_api_key_stages_nothing_and_says_so():
    with mock.patch.object(yt, "resolve_api_key", return_value=None):
        r = yt.fetch_youtube_trends(country="US")
    assert r["method"] == "no_api_key"
    assert "no_api_key" in r["flags"]
    assert yt.observations_from_result(r) == []


def test_http_error_reports_reason_and_stages_nothing():
    payload = {"error": {"message": "quotaExceeded"}}
    with mock.patch.object(yt, "resolve_api_key", return_value="k"), \
         mock.patch.object(yt.requests, "get", return_value=_Resp(payload, 403)):
        r = yt.fetch_youtube_trends(country="US")
    assert r["method"] == "fetch_failed"
    assert "quotaExceeded" in r["note"]
    assert yt.observations_from_result(r) == []


def test_empty_chart_stages_nothing():
    with mock.patch.object(yt, "resolve_api_key", return_value="k"), \
         mock.patch.object(yt.requests, "get", return_value=_Resp({"items": []})):
        r = yt.fetch_youtube_trends(country="GB")
    assert r["method"] == "fetch_failed"
    assert yt.observations_from_result(r) == []


def test_success_emits_only_shareable_aggregate_rows():
    payload = {"items": [_item(1000, 100, 10), _item(2000, 100, 20, "PT2M")]}
    with mock.patch.object(yt, "resolve_api_key", return_value="k"), \
         mock.patch.object(yt.requests, "get", return_value=_Resp(payload)):
        r = yt.fetch_youtube_trends(country="DE")
    assert r["method"] == "youtube_data_api"
    rows = yt.observations_from_result(r)
    assert rows, "a successful fetch must produce observation rows"
    for row in rows:
        # Exactly the shareable schema — no extra keys, no banned keys.
        assert set(row) == set(SHAREABLE), set(row) ^ set(SHAREABLE)
        assert not (set(row) & set(BANNED))
        assert row["platform"] == "youtube"
        assert row["source"] == "youtube_data_api"
        assert row["country"] == "DE"
        assert isinstance(row["metric_value"], float)
    # The sample size travels with the metrics so a consumer can weight them.
    assert "sample_size" in {r_["metric_name"] for r_ in rows}


def test_category_id_becomes_the_industry_dimension():
    payload = {"items": [_item(500, 50, 5)]}
    with mock.patch.object(yt, "resolve_api_key", return_value="k"), \
         mock.patch.object(yt.requests, "get", return_value=_Resp(payload)):
        r = yt.fetch_youtube_trends(country="US", category_id="20")
    rows = yt.observations_from_result(r)
    assert rows and {row["industry"] for row in rows} == {"yt_category_20"}


def test_youtube_rows_pass_the_federation_validator():
    """The vocabulary allow-list must actually admit these rows — otherwise the
    collector stages data that can never be contributed (it silently did at
    first: bad_data_type / bad_source / platform not in ['tiktok'])."""
    from federation.contribute import validate_shareable
    payload = {"items": [_item(1000, 100, 10), _item(2000, 100, 20, "PT2M")]}
    with mock.patch.object(yt, "resolve_api_key", return_value="k"), \
         mock.patch.object(yt.requests, "get", return_value=_Resp(payload)):
        r = yt.fetch_youtube_trends(country="US")
    rows = yt.observations_from_result(r)
    assert rows
    for row in rows:
        assert validate_shareable(row) == [], (row, validate_shareable(row))


def test_trending_benchmark_stays_distinct_from_perf_benchmark():
    """A median over trending videos is not measured own-account performance;
    keeping the types separate stops one being read as the other."""
    from federation.validate import VALID_DATA_TYPES
    assert "trending_benchmark" in VALID_DATA_TYPES
    assert "perf_benchmark" in VALID_DATA_TYPES
    assert "trending_benchmark" != "perf_benchmark"
