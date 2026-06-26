"""Stage 4 acceptance (K4): with no headers/proxy, the fetcher returns a
fetch_failed-labeled fallback — never raises, never fabricates. With valid
headers + a mocked endpoint, it returns live items labeled external_best_effort."""
import fetch_trends as ft


def test_no_headers_returns_labeled_fallback_never_raises():
    res = ft.fetch_trending_hashtags(country="US")  # no headers
    assert res["items"] == []  # no cache => empty, NOT fabricated
    assert res["confidence"] == "LOW"
    assert res["method"] == "cache_or_community_fallback"
    assert "fetch_failed" in res["flags"]
    assert res["fetched_at"] is None
    assert any(f.startswith("reason:") for f in res["flags"])


def test_fallback_uses_cache_when_available_but_labels_stale():
    cache = {"US:": [{"hashtag": "#cachedtag", "rank": 1}]}
    res = ft.fetch_trending_hashtags(country="US", cache=cache)
    assert res["items"] == [{"hashtag": "#cachedtag", "rank": 1}]
    assert "stale_possible" in res["flags"]
    assert res["confidence"] == "LOW"  # cached data is never presented as fresh


def test_live_success_labeled_external_best_effort(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"list": [
                {"hashtag_name": "#saas", "rank": 1, "publish_cnt": 1000, "video_views": 50000},
            ]}}

    class FakeRequests:
        @staticmethod
        def get(*a, **k):
            return FakeResp()

    monkeypatch.setattr(ft, "requests", FakeRequests)
    res = ft.fetch_trending_hashtags(country="US", headers={"user-sign": "x"})
    assert res["method"] == "creative_center_live"
    assert res["confidence"] == "MEDIUM"  # external estimate caps below HIGH
    assert "external_best_effort" in res["flags"]
    assert res["items"][0]["hashtag"] == "#saas"
    assert res["fetched_at"] is not None


def test_empty_live_response_degrades(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"list": []}}

    class FakeRequests:
        @staticmethod
        def get(*a, **k):
            return FakeResp()

    monkeypatch.setattr(ft, "requests", FakeRequests)
    res = ft.fetch_trending_hashtags(country="US", headers={"user-sign": "x"})
    assert "fetch_failed" in res["flags"]
    assert any("empty_response" in f for f in res["flags"])


def test_network_error_degrades(monkeypatch):
    class FakeRequests:
        @staticmethod
        def get(*a, **k):
            raise RuntimeError("connection_refused")

    monkeypatch.setattr(ft, "requests", FakeRequests)
    res = ft.fetch_trending_hashtags(country="US", headers={"user-sign": "x"})
    assert res["method"] == "cache_or_community_fallback"
    assert "fetch_failed" in res["flags"]
