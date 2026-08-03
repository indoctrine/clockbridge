"""Unit tests for Flusher.

We drive tick() directly instead of spinning up the thread. The one thread-based test exists purely 
to confirm start()/stop() don't deadlock and it does not rely on wall-clock behaviour for correctness.
"""
import os
import sys
import time
import pytest

sys.path.append(os.path.abspath('../'))

from flusher import Flusher
from timer_store import TimerStore

class FakeEs:
    """Minimal stand-in that allows testing script health and push behaviour per call."""
    def __init__(self, healthy=True, push_ok=True):
        self.healthy = healthy
        self.push_ok = push_ok
        self.pushed = []
        self.health_raises = False
        self.push_raises = False

    def health_check(self):
        if self.health_raises:
            raise RuntimeError("simulated health check failure")
        return self.healthy

    def push(self, data, action="create"):
        if self.push_raises:
            raise RuntimeError("simulated push failure")
        self.pushed.append((action, data))
        return self.push_ok

@pytest.fixture
def store():
    s = TimerStore(":memory:")
    yield s
    s.close()


def _queue_pending(store, description="x"):
    """Start a timer, sleep briefly so end > start, stop it -> one pending_flush row."""
    started = store.start(description=description)["started"]
    time.sleep(0.01)
    store.stop(started["id"])
    return started["id"]


class TestTick:
    def test_tick_with_no_rows_is_a_noop(self, store):
        # Nothing pushed when pending rows empty
        es = FakeEs()
        f = Flusher(store, es)
        f.tick()
        assert es.pushed == []

    def test_tick_pushes_and_deletes(self, store):
        es = FakeEs()
        timer_id = _queue_pending(store)
        f = Flusher(store, es)
        f.tick()

        assert len(es.pushed) == 1
        assert es.pushed[0][0] == "create"
        assert es.pushed[0][1]["id"] == timer_id
        # Row deleted after successful push.
        assert store.claim_due() == []

    def test_tick_defers_when_es_unhealthy(self, store):
        es = FakeEs(healthy=False)
        timer_id = _queue_pending(store)
        f = Flusher(store, es)
        f.tick()
        # Nothing pushed, row still there (but next_retry_at was advanced by claim).
        assert es.pushed == []
        # Force it back to due for the assertion.
        rows = store._conn.execute(
            "SELECT id FROM timers WHERE status='pending_flush'"
        ).fetchall()
        assert len(rows) == 1 and rows[0]["id"] == timer_id

    def test_tick_keeps_row_when_push_returns_false(self, store):
        es = FakeEs(push_ok=False)
        timer_id = _queue_pending(store)
        f = Flusher(store, es)
        f.tick()
        # Push was attempted but failed; row must not be deleted.
        assert len(es.pushed) == 1
        rows = store._conn.execute(
            "SELECT id FROM timers WHERE status='pending_flush'"
        ).fetchall()
        assert len(rows) == 1 and rows[0]["id"] == timer_id

    def test_tick_keeps_row_when_push_raises(self, store):
        es = FakeEs()
        es.push_raises = True
        timer_id = _queue_pending(store)
        f = Flusher(store, es)
        f.tick()  # must not propagate the exception
        rows = store._conn.execute(
            "SELECT id FROM timers WHERE status='pending_flush'"
        ).fetchall()
        assert len(rows) == 1 and rows[0]["id"] == timer_id

    def test_tick_survives_health_check_exception(self, store):
        es = FakeEs()
        es.health_raises = True
        _queue_pending(store)
        f = Flusher(store, es)
        f.tick()  # must not raise
        assert es.pushed == []

    def test_tick_stamps_at_timestamp(self, store):
        es = FakeEs()
        _queue_pending(store)
        f = Flusher(store, es)
        f.tick()
        assert "@timestamp" in es.pushed[0][1]


class TestThreadLifecycle:
    def test_start_and_stop_do_not_deadlock(self, store):
        es = FakeEs()
        f = Flusher(store, es, interval_seconds=0.05)
        f.start()
        # Let the loop tick once or twice.
        time.sleep(0.12)
        f.stop(timeout=2)
        assert not f._thread.is_alive()

    def test_start_twice_is_idempotent(self, store):
        es = FakeEs()
        f = Flusher(store, es, interval_seconds=0.05)
        f.start()
        thread1 = f._thread
        f.start()
        thread2 = f._thread
        assert thread1 is thread2
        f.stop(timeout=2)
