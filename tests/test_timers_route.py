"""Tests for the /api/timers routes.

These use the client fixture (from conftest) and the timer_store fixture,
which swaps a fresh in-memory TimerStore onto app.config for each test.
Elasticsearch is stubbed via monkeypatching app_module.es
"""
import os
import sys
import time

import app as app_module

sys.path.append(os.path.abspath('../'))


def _es_up(monkeypatch, push_returns=True, captured=None):
    """Monkeypatch the shared Elastic instance to be healthy and record pushes."""
    if captured is None:
        captured = []
    monkeypatch.setattr(app_module.es, "health_check", lambda: True)
    monkeypatch.setattr(
        app_module.es, "push",
        lambda data, action="create": captured.append((action, data)) or push_returns,
    )
    return captured


def _es_down(monkeypatch):
    monkeypatch.setattr(app_module.es, "health_check", lambda: False)
    monkeypatch.setattr(
        app_module.es, "push",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("push should not be attempted")),
    )


class TestStart:
    def test_start_from_clean_state_returns_new_timer(self, client, timer_store, monkeypatch):
        _es_up(monkeypatch)
        res = client.post("/api/timers", json={"description": "focus"})
        assert res.status_code == 201
        body = res.get_json()
        assert body["stopped"] is None
        assert body["started"]["description"] == "focus"
        assert "id" in body["started"]
        assert "start" in body["started"]

    def test_start_when_running_auto_stops_and_pushes_prior(self, client, timer_store, monkeypatch):
        captured = _es_up(monkeypatch)

        first = client.post("/api/timers", json={"description": "A"}).get_json()
        time.sleep(0.01)
        second = client.post("/api/timers", json={"description": "B"}).get_json()

        # The prior timer is returned as 'stopped' with a completed timeInterval.
        assert second["stopped"]["id"] == first["started"]["id"]
        assert "end" in second["stopped"]["timeInterval"]
        # And it was pushed to ES as part of the start request.
        assert len(captured) == 1
        pushed_action, pushed_data = captured[0]
        assert pushed_action == "create"
        assert pushed_data["id"] == first["started"]["id"]
        # The new timer is running.
        get_res = client.get("/api/timers")
        assert get_res.status_code == 200
        assert get_res.get_json()["description"] == "B"

    def test_start_with_no_body_still_works(self, client, timer_store, monkeypatch):
        _es_up(monkeypatch)
        res = client.post("/api/timers")
        assert res.status_code == 201
        assert res.get_json()["started"]["description"] is None

    def test_start_when_es_down_still_starts_new_timer(self, client, timer_store, monkeypatch):
        """The user should be able to start a new timer even if Elasticsearch is
        down -- the prior timer's push simply falls to the flusher."""
        # Start a timer while ES is healthy.
        _es_up(monkeypatch)
        first = client.post("/api/timers", json={"description": "A"}).get_json()
        # Now ES goes down; starting a new one must still succeed.
        _es_down(monkeypatch)
        res = client.post("/api/timers", json={"description": "B"})
        assert res.status_code == 201
        body = res.get_json()
        assert body["stopped"]["id"] == first["started"]["id"]
        # Prior timer is in pending_flush, waiting for the flusher.
        claimed = timer_store.claim_due()
        assert len(claimed) == 1
        assert claimed[0][0] == first["started"]["id"]


class TestGet:
    def test_get_when_none_running_returns_204(self, client, timer_store):
        res = client.get("/api/timers")
        assert res.status_code == 204

    def test_get_returns_running_timer(self, client, timer_store, monkeypatch):
        _es_up(monkeypatch)
        started = client.post("/api/timers", json={"description": "focus"}).get_json()
        res = client.get("/api/timers")
        assert res.status_code == 200
        body = res.get_json()
        assert body["id"] == started["started"]["id"]
        assert body["description"] == "focus"


class TestStop:
    def test_stop_running_timer_pushes_and_returns_201(self, client, timer_store, monkeypatch):
        captured = _es_up(monkeypatch)
        started = client.post("/api/timers", json={"description": "focus"}).get_json()
        time.sleep(0.01)
        res = client.post(f"/api/timers/{started['started']['id']}/stop")
        assert res.status_code == 201
        body = res.get_json()
        assert body["id"] == started["started"]["id"]
        assert "@timestamp" in body
        assert body["timeInterval"]["duration"] >= 0
        # And the row is gone from pending_flush.
        assert timer_store.claim_due() == []
        # And the ES push was recorded.
        assert len(captured) == 1
        assert captured[0][0] == "create"

    def test_stop_when_es_down_returns_202_and_leaves_pending_flush(self, client, timer_store, monkeypatch):
        # Start with ES up.
        _es_up(monkeypatch)
        started = client.post("/api/timers", json={"description": "focus"}).get_json()
        time.sleep(0.01)
        # ES goes down between start and stop.
        _es_down(monkeypatch)
        res = client.post(f"/api/timers/{started['started']['id']}/stop")
        assert res.status_code == 202
        body = res.get_json()
        assert body["status"] == "pending_flush"
        # Row is still there for the flusher.
        claimed = timer_store.claim_due()
        assert len(claimed) == 1
        assert claimed[0][0] == started["started"]["id"]

    def test_stop_unknown_id_returns_404(self, client, timer_store):
        res = client.post("/api/timers/not-a-real-id/stop")
        assert res.status_code == 404

    def test_stop_already_stopped_returns_404(self, client, timer_store, monkeypatch):
        _es_up(monkeypatch)
        started = client.post("/api/timers", json={"description": "focus"}).get_json()
        time.sleep(0.01)
        client.post(f"/api/timers/{started['started']['id']}/stop")
        # Second stop on the same id is a 404: it's no longer running.
        res = client.post(f"/api/timers/{started['started']['id']}/stop")
        assert res.status_code == 404


class TestCancel:
    def test_cancel_running_returns_204(self, client, timer_store, monkeypatch):
        _es_up(monkeypatch)
        started = client.post("/api/timers", json={"description": "oops"}).get_json()
        # cancel should not push anything: swap in an assertion.
        monkeypatch.setattr(
            app_module.es, "push",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("cancel should not push")),
        )
        res = client.delete(f"/api/timers/{started['started']['id']}")
        assert res.status_code == 204
        assert client.get("/api/timers").status_code == 204

    def test_cancel_unknown_returns_404(self, client, timer_store):
        res = client.delete("/api/timers/not-a-real-id")
        assert res.status_code == 404


class TestFlusherIntegration:
    """Not a full flusher test (see test_flusher.py) -- just proves the
    routes cooperate with claim_due correctly."""

    def test_stop_when_es_down_then_flusher_tick_pushes(self, client, timer_store, monkeypatch):
        from flusher import Flusher

        _es_up(monkeypatch)
        started = client.post("/api/timers", json={"description": "A"}).get_json()
        time.sleep(0.01)
        _es_down(monkeypatch)
        res = client.post(f"/api/timers/{started['started']['id']}/stop")
        assert res.status_code == 202

        # ES comes back. A flusher tick should push and delete the row.
        captured = _es_up(monkeypatch)
        f = Flusher(timer_store, app_module.es)
        # backoff_base=0 in the store side ensures the row is due; the flusher
        # calls claim_due with defaults, but the row's next_retry_at was set
        # to now-ish by the stop path, so it will be due after we sleep briefly.
        time.sleep(0.05)
        f.tick()
        # Push happened.
        assert any(c[1]["id"] == started["started"]["id"] for c in captured)
        # Row is gone.
        assert timer_store.claim_due() == []
