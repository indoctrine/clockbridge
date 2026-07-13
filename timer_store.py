"""
AUTHOR:     Beck D.
DATE:       2026-
PURPOSE:    SQLite-backed store for in-flight timers and pending Elasticsearch flushes.

The store owns two lifecycle states:

  running       - a timer the user has started; the row holds description /
                  project / task metadata and the start timestamp. Only one
                  such row may exist at a time; the partial unique index
                  enforces this at the database layer so a race between two
                  concurrent 'start' clicks cannot produce two running rows.

  pending_flush - a timer that has been stopped (so 'end' and 'duration' are
                  now populated in the entry blob) but whose push to
                  Elasticsearch has not yet succeeded. A background flusher
                  scans these rows and retries. Rows are deleted only after
                  a successful push, so a worker crash or ES outage cannot
                  drop a completed entry.

Concurrency notes: with `gunicorn -w 4` each worker will hold its own
connection and its own flusher thread. Correctness is preserved because
`claim_due` uses an atomic UPDATE ... RETURNING to hand each due row to
exactly one worker; the 'start' path relies on the partial unique index;
and every write goes through a BEGIN IMMEDIATE transaction so writer
races serialise cleanly.
"""

import json
import logging
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

TS_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

def _now_utc():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.astimezone(timezone.utc).strftime(TS_FORMAT)


SCHEMA = """
CREATE TABLE IF NOT EXISTS timers (
    id            TEXT PRIMARY KEY,
    start         TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('running', 'pending_flush')),
    entry         TEXT NOT NULL,
    next_retry_at TEXT,
    retry_count   INTEGER NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS one_running
    ON timers(status) WHERE status = 'running';

CREATE INDEX IF NOT EXISTS pending_by_due
    ON timers(next_retry_at) WHERE status = 'pending_flush';
"""

class ConflictError(Exception):
    """Raised when the store rejects an operation because of the single-running task."""

class NotFoundError(Exception):
    """Raised when a timer id has no matching row (or no matching row in the expected state)."""

class TimerStore:
    """Thin CRUD around the timers table. All mutations go through _tx()."""

    def __init__(self, path):
        self.path = path
        # check_same_thread=False allows the flusher thread to reuse the connection.
        # We keep the connection serialised via _lock so concurrent access is still safe.
        # isolation_level=None puts us in autocommit and lets us issue explicit
        # BEGIN IMMEDIATE, which is used forr controlled write transactions in SQLite.
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()

        # WAL improves concurrency between the request threads and the flusher
        # foreign_keys is on for future-proofing (no FKs today).
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)

    @contextmanager
    def _tx(self):
        """Serialise writers behind an application-level lock plus BEGIN IMMEDIATE.
        The lock protects the single shared connection object; BEGIN IMMEDIATE
        promotes to the reserved lock so a concurrent writer in another process
        (or another worker's flusher) blocks instead of racing."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                # contextmanager returns via yield, temporarily returning control flow to caller
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")

    # ---- entry helpers -----------------------------------------------------

    @staticmethod
    def _running_entry(timer_id, description, project, project_id, task):
        """Shape of the in-progress entry blob. Kept close to the completed
        Clockify-shaped payload so stop() only has to add timeInterval."""
        return {
            "id": timer_id,
            "description": description,
            "project": project,
            "projectId": project_id,
            "task": task,
        }

    @staticmethod
    def _row_to_running_dict(row):
        entry = json.loads(row["entry"])
        return {"id": row["id"], "start": row["start"], **entry}

    # ---- lifecycle ---------------------------------------------------------

    def start(self, description=None, project=None, project_id=None, task=None):
        """Start a new running timer.

        If a timer is already running, that row is transitioned to pending_flush
        (with end = now) and the flusher will push it once Elasticsearch is
        reachable. This means starting a new timer stops the old one, preserving
        the single-running invariant. The transition and the new INSERT happen
        in one transaction, so a crash mid-call can't leave you with two running
        timers or zero.

        Returns {"started": <new_timer>, "stopped": <prev_or_None>}. The caller
        can attempt a synchronous push of `stopped` for lower latency, but is
        not required to -- the flusher will handle it either way.
        """
        new_id = str(uuid.uuid4())
        start_ts = _iso(_now_utc())
        new_entry = self._running_entry(new_id, description, project, project_id, task)

        with self._tx() as c:
            prev = c.execute(
                "SELECT id, start, entry FROM timers WHERE status = 'running'"
            ).fetchone()
            stopped_entry = None
            if prev is not None:
                stopped_entry = self._finalise_entry(prev)
                # next_retry_at = now: the caller can try a synchronous push
                # immediately, and if it fails or the caller crashes the
                # flusher will pick it up on its next tick.
                c.execute(
                    "UPDATE timers SET status = 'pending_flush', entry = ?, next_retry_at = ? "
                    "WHERE id = ?",
                    (json.dumps(stopped_entry), _iso(_now_utc()), prev["id"]),
                )
            try:
                c.execute(
                    "INSERT INTO timers(id, start, status, entry) VALUES(?, ?, 'running', ?)",
                    (new_id, start_ts, json.dumps(new_entry)),
                )
            except sqlite3.IntegrityError as exc:
                # Within one BEGIN IMMEDIATE this shouldn't happen because we 
                # just transitioned the previous running row above, but if the 
                # invariant is ever violated we raise it explicitly.
                raise ConflictError("A running timer already exists") from exc

        started = {"id": new_id, "start": start_ts, **new_entry}
        return {"started": started, "stopped": stopped_entry}

    def get_running(self):
        """Return the currently-running timer, or None. Used to update a
        reloaded browser tab."""
        row = self._conn.execute(
            "SELECT id, start, entry FROM timers WHERE status = 'running'"
        ).fetchone()
        return self._row_to_running_dict(row) if row else None

    def _finalise_entry(self, row):
        """Given a running row, produce the completed entry with end/duration filled in."""
        entry = json.loads(row["entry"])
        start_dt = datetime.strptime(row["start"], TS_FORMAT)
        end_dt = _now_utc()
        entry["timeInterval"] = {
            "start": row["start"],
            "end": _iso(end_dt),
            "duration": int((end_dt - start_dt).total_seconds()),
        }
        return entry

    def stop(self, timer_id):
        """Stop the running timer with the given id and return the completed entry.

        The row transitions to pending_flush rather than being deleted; the
        caller (route or flusher) is responsible for the ES push, and
        mark_flushed() deletes only on success. This is what protects a
        completed entry from being lost to a worker crash between "stop" and
        "push".
        """
        with self._tx() as c:
            row = c.execute(
                "SELECT id, start, entry FROM timers WHERE id = ? AND status = 'running'",
                (timer_id,),
            ).fetchone()
            if row is None:
                raise NotFoundError(f"No running timer with id {timer_id}")

            entry = self._finalise_entry(row)
            c.execute(
                "UPDATE timers SET status = 'pending_flush', entry = ?, next_retry_at = ? "
                "WHERE id = ?",
                (json.dumps(entry), _iso(_now_utc()), timer_id),
            )
        return entry

    def cancel(self, timer_id):
        """Discard a running timer without pushing anything to Elasticsearch.

        Returns True if a row was deleted, False if no running timer matched.
        Deliberately scoped to 'running' rows only: cancelling a pending_flush
        row would silently lose a completed entry that the user expects to
        appear on their dashboard.
        """
        with self._tx() as c:
            cur = c.execute(
                "DELETE FROM timers WHERE id = ? AND status = 'running'",
                (timer_id,),
            )
            return cur.rowcount > 0

    def mark_flushed(self, timer_id):
        """Delete a row after its entry has been successfully pushed to ES."""
        with self._tx() as c:
            c.execute("DELETE FROM timers WHERE id = ?", (timer_id,))

    # ---- retry queue -------------------------------------------------------

    def claim_due(self, limit=10, backoff_base_seconds=30, backoff_max_seconds=3600):
        """Atomically claim due pending_flush rows and reschedule them.

        Returns a list of (timer_id, entry_dict, retry_count) for rows the
        caller should attempt to push. The claim step also updates each
        claimed row's next_retry_at using exponential backoff so that:

          - if the caller's push succeeds, mark_flushed() deletes the row
            and the rescheduled next_retry_at was harmless.
          - if the caller's push fails or the worker crashes, the row will
            not be reclaimed until the new next_retry_at, giving ES time to
            recover instead of getting hammered.

        Multiple flusher threads (across gunicorn workers) can call this
        concurrently: each row's UPDATE ... RETURNING is atomic so a given
        row is handed to exactly one caller per tick.
        """
        now_dt = _now_utc()
        now_iso = _iso(now_dt)
        claimed = []

        with self._tx() as c:
            rows = c.execute(
                """
                SELECT id, entry, retry_count FROM timers
                WHERE status = 'pending_flush'
                  AND (next_retry_at IS NULL OR next_retry_at <= ?)
                ORDER BY next_retry_at ASC
                LIMIT ?
                """,
                (now_iso, limit),
            ).fetchall()

            for r in rows:
                new_count = r["retry_count"] + 1
                # Cap the exponent so backoff * 2**n doesn't overflow well
                # before it hits backoff_max_seconds anyway.
                exp = min(new_count, 12)
                delay = min(backoff_base_seconds * (2 ** exp), backoff_max_seconds)
                next_at = _iso(now_dt + timedelta(seconds=delay))
                c.execute(
                    "UPDATE timers SET retry_count = ?, next_retry_at = ? WHERE id = ?",
                    (new_count, next_at, r["id"]),
                )
                claimed.append((r["id"], json.loads(r["entry"]), new_count))

        return claimed

    def close(self):
        """Close the underlying connection. Mainly used for tests."""
        self._conn.close()
