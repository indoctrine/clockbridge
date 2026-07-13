"""Unit tests for TimerStore.

These exercise the store directly (no Flask) to nail down the invariants
the routes and flusher lean on: single running timer, correct stop/cancel
semantics, and claim_due handing each due row to exactly one caller.
"""
import os
import sys
import sqlite3
import time
import pytest

sys.path.append(os.path.abspath('../'))

from timer_store import TimerStore, ConflictError, NotFoundError


@pytest.fixture
def store():
    s = TimerStore(":memory:")
    yield s
    s.close()


class TestSingleRunningInvariant:
    """The partial unique index is what enforces single-running; these check
    that the store's public surface respects it and surfaces useful state."""

    def test_start_when_none_running_returns_started_no_stopped(self, store):
        # Tests start normally when no other timers running
        result = store.start(description="focus", project=None)
        assert result["stopped"] is None
        assert result["started"]["description"] == "focus"
        assert store.get_running()["id"] == result["started"]["id"]

    def test_start_when_one_running_auto_stops_prior(self, store):
        # Verifies that new timer stops prior running timer
        first = store.start(description="A")["started"]
        second = store.start(description="B")
        # Prior timer surfaces in the 'stopped' key with a completed timeInterval.
        assert second["stopped"]["id"] == first["id"]
        assert "end" in second["stopped"]["timeInterval"]
        assert second["stopped"]["timeInterval"]["duration"] >= 0
        # And exactly one running row now, with the new id.
        running = store.get_running()
        assert running["id"] == second["started"]["id"]
        assert running["description"] == "B"

    def test_get_running_none_when_empty(self, store):
        assert store.get_running() is None


class TestStop:
    def test_stop_transitions_to_pending_flush(self, store):
        started = store.start(description="ship it")["started"]
        # A minimum measurable duration so end > start.
        time.sleep(0.01)
        entry = store.stop(started["id"])
        assert entry["id"] == started["id"]
        assert entry["timeInterval"]["start"] == started["start"]
        assert "end" in entry["timeInterval"]
        assert entry["timeInterval"]["duration"] >= 0
        # Confirm row is not deleted as mark_flushed() not called yet
        assert store.get_running() is None
        claimed = store.claim_due()
        assert len(claimed) == 1
        assert claimed[0][0] == started["id"]

    def test_stop_unknown_id_raises(self, store):
        with pytest.raises(NotFoundError):
            store.stop("not-a-real-id")

    def test_stop_pending_flush_row_raises(self, store):
        """A row that's already been stopped can't be stopped again, otherwise
        the flusher and the stop route could race to double-stop and the timeInterval
        would get overwritten with a later end."""
        started = store.start()["started"]
        store.stop(started["id"])
        with pytest.raises(NotFoundError):
            store.stop(started["id"])


class TestCancel:
    def test_cancel_running_deletes_row(self, store):
        # Confirm that cancelling in-flight timer removes table entry
        started = store.start(description="oops")["started"]
        assert store.cancel(started["id"]) is True
        assert store.get_running() is None

    def test_cancel_unknown_returns_false(self, store):
        assert store.cancel("not-a-real-id") is False

    def test_cancel_will_not_drop_pending_flush(self, store):
        """A stopped timer represents work the user expects to see on their
        dashboard, so cancel must not silently delete pending_flush rows."""
        started = store.start()["started"]
        store.stop(started["id"])
        assert store.cancel(started["id"]) is False
        # Still there for the flusher.
        claimed = store.claim_due()
        assert len(claimed) == 1


class TestMarkFlushed:
    def test_mark_flushed_removes_row(self, store):
        started = store.start()["started"]
        store.stop(started["id"])
        # Delete entry
        store.mark_flushed(started["id"])
        assert store.claim_due() == []


class TestClaimDue:
    def test_no_pending_flush_returns_empty(self, store):
        assert store.claim_due() == []
        store.start()  # a running row is not due
        assert store.claim_due() == []

    def test_claim_returns_stopped_rows(self, store):
        s1 = store.start(description="one")["started"]
        store.stop(s1["id"])
        s2 = store.start(description="two")["started"]
        store.stop(s2["id"])

        claimed = store.claim_due()
        ids = {c[0] for c in claimed}
        assert ids == {s1["id"], s2["id"]}

    def test_claim_reschedules_next_retry_at(self, store):
        """After a claim, the row's next_retry_at is pushed into the future,
        so an immediate second claim finds nothing. This is what prevents
        two flusher ticks in the same second from double-pushing."""
        started = store.start()["started"]
        store.stop(started["id"])

        first = store.claim_due(backoff_base_seconds=60)
        assert len(first) == 1
        # Same tick, no rows due now.
        second = store.claim_due(backoff_base_seconds=60)
        assert second == []

    def test_claim_increments_retry_count(self, store):
        started = store.start()["started"]
        store.stop(started["id"])
        # Ignore ID and timestamp
        _, _, count1 = store.claim_due(backoff_base_seconds=0)[0]
        # backoff_base=0 keeps next_retry_at at 'now', so the row is due again.
        _, _, count2 = store.claim_due(backoff_base_seconds=0)[0]
        assert count1 == 1
        assert count2 == 2


class TestDatabaseLevelInvariant:
    """A regression test against the invariant itself: even if a bug in
    higher layers tried to insert two running rows, the DB says no."""

    def test_partial_unique_index_blocks_second_running_insert(self, store):
        store.start()
        with pytest.raises(sqlite3.IntegrityError):
            # Reach past the public API to prove the DB is doing the work.
            store._conn.execute(
                "INSERT INTO timers(id, start, status, entry) "
                "VALUES('duplicate', '2026-01-01T00:00:00+0000', 'running', '{}')"
            )
