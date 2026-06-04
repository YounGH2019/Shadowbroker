"""Regression tests for GitHub #375 production-readiness fixes."""

import os

import pytest


class TestDevBindHost:
    def test_defaults_to_loopback(self, monkeypatch):
        monkeypatch.delenv("SHADOWBROKER_DEV_BIND_ALL", raising=False)
        from main import _dev_uvicorn_bind_host

        assert _dev_uvicorn_bind_host() == "127.0.0.1"

    @pytest.mark.parametrize("value", ("1", "true", "yes", "on", "TRUE"))
    def test_bind_all_opt_in(self, monkeypatch, value):
        monkeypatch.setenv("SHADOWBROKER_DEV_BIND_ALL", value)
        from main import _dev_uvicorn_bind_host

        assert _dev_uvicorn_bind_host() == "0.0.0.0"


class TestDataStoreSnapshots:
    def test_deepcopy_snapshot_isolated_from_store(self):
        from services.fetchers import _store

        original = [{"title": "baseline"}]
        with _store._data_lock:
            _store.latest_data["news"] = list(original)
        snap = _store.get_latest_data_deepcopy_snapshot()
        snap["news"][0]["title"] = "mutated"
        with _store._data_lock:
            assert _store.latest_data["news"][0]["title"] == "baseline"

    def test_subset_deepcopy_isolated(self):
        from services.fetchers import _store

        with _store._data_lock:
            _store.latest_data["news"] = [{"title": "subset"}]
        snap = _store.get_latest_data_subset("news")
        snap["news"][0]["title"] = "changed"
        with _store._data_lock:
            assert _store.latest_data["news"][0]["title"] == "subset"


class TestHeavyFetchExecutorRouting:
    def test_slow_tier_uses_slow_executor(self):
        from services.data_fetcher import (
            _SLOW_EXECUTOR,
            _SHARED_EXECUTOR,
            _executor_for_task_label,
        )

        assert _executor_for_task_label("slow-tier-refresh") is _SLOW_EXECUTOR
        assert _executor_for_task_label("startup-heavy-warm") is _SLOW_EXECUTOR
        assert _executor_for_task_label("fast-tier-refresh") is _SHARED_EXECUTOR


class TestLiveDataFullEndpoint:
    def test_live_data_supports_etag_304(self, client):
        r1 = client.get("/api/live-data")
        assert r1.status_code == 200
        etag = r1.headers.get("etag")
        assert etag
        r2 = client.get("/api/live-data", headers={"If-None-Match": etag})
        assert r2.status_code == 304
        assert r2.headers.get("etag") == etag
