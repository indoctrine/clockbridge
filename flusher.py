"""
AUTHOR:     Beck D.
DATE:       2026-
PURPOSE:    Background retry loop for pending_flush timers.

The flusher polls the TimerStore for pending_flush rows whose next_retry_at
is due, attempts to push each one to Elasticsearch, and deletes the row on
success. On failure the row is left as-is with an updated backoff, so the
next tick will retry it later.

The loop runs in a daemon thread inside each gunicorn worker. Multiple
workers polling the same table is safe because `TimerStore.claim_due`
atomically reschedules each row it hands out, so a given row is worked by
exactly one worker per tick.
"""

import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class Flusher:
    """Drains pending_flush timers into Elasticsearch on a fixed interval."""
    def __init__(self, store, es, interval_seconds=15, batch_size=10):
        self.store = store
        self.es = es
        self.interval = interval_seconds
        self.batch_size = batch_size
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        """Start the background thread. Safe to call multiple times; only the first has effect."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="clockbridge-flusher", daemon=True
        )
        self._thread.start()
        logger.info("Flusher thread started (interval=%ss, batch=%d)",
                    self.interval, self.batch_size)

    def stop(self, timeout=5):
        """Signal the loop to exit and wait briefly for it to do so."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self.tick()
            except Exception:
                # A thrown exception must not kill the thread, the whole point
                # of this loop is durable retry. Log and continue.
                logger.exception("Flusher tick raised; continuing")
            # wait() returns True if the event was set, letting stop() short-circuit sleep.
            if self._stop_event.wait(self.interval):
                break
        logger.info("Flusher thread exiting")

    def tick(self):
        """One pass of: claim due rows, check ES health, push each one.

        Broken out as a public method so tests can drive the loop
        deterministically without spinning up a thread.
        """
        claimed = self.store.claim_due(limit=self.batch_size)
        if not claimed:
            return

        # One health check per batch rather than per row. If ES is not green,
        # we don't try any pushes this tick but claim_due has already
        # advanced next_retry_at, so we'll try again after the backoff.
        try:
            healthy = self.es.health_check()
        except Exception:
            logger.exception("Flusher: health_check raised; deferring %d entries", len(claimed))
            return

        if not healthy:
            logger.info("Flusher: Elasticsearch not green; deferring %d entries", len(claimed))
            return

        for timer_id, entry, retry_count in claimed:
            self._push_one(timer_id, entry, retry_count)

    def _push_one(self, timer_id, entry, retry_count):
        # Stamp @timestamp on the way out, the same way the routes do, so
        # dashboards see a consistent field regardless of which producer wrote
        # the entry.
        entry.setdefault(
            "@timestamp",
            datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z"),
        )

        try:
            pushed = self.es.push(entry, "create")
        except Exception:
            logger.exception(
                "Flusher: push raised for %s (retry %d); will retry", timer_id, retry_count
            )
            return

        if pushed:
            self.store.mark_flushed(timer_id)
            logger.info("Flusher: pushed %s after %d retries", timer_id, retry_count)
        else:
            logger.warning(
                "Flusher: push returned false for %s (retry %d); will retry",
                timer_id, retry_count,
            )
