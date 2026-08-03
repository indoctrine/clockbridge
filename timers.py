"""
AUTHOR:     Beck D.
DATE:       2026-
PURPOSE:    Flask blueprint exposing the timer lifecycle over HTTP.

Routes:
    POST   /api/timers            Start a new running timer. If one is
                                  already running, that timer is atomically
                                  stopped (transitioned to pending_flush)
                                  and the new one is started in the same
                                  transaction. Returns both.
    GET    /api/timers            Return the currently-running timer, or
                                  204 if none. Lets a reloaded browser tab
                                  repopulate its UI.
    POST   /api/timers/<id>/stop  Stop the running timer with this id and
                                  attempt a synchronous push to
                                  Elasticsearch. On success returns 201 with
                                  the completed entry; on failure returns
                                  202 -- the row remains in pending_flush
                                  and the flusher will retry.
    DELETE /api/timers/<id>       Discard a running timer without pushing
                                  anything.

Dependencies (store and es) are looked up via current_app.config so that
tests can substitute a fresh TimerStore per test without patching module
globals.
"""

import json
import logging
from datetime import datetime
from flask import Blueprint, Response, current_app, request
from timer_store import ConflictError, NotFoundError
from payload import Payload

logger = logging.getLogger(__name__)

# Creates the blueprint for /api/timers and its child routes
timers_bp = Blueprint("timers", __name__, url_prefix="/api/timers")

def _store():
    return current_app.config["TIMER_STORE"]

def _es():
    return current_app.config["ES"]

def _json(body, status):
    return Response(json.dumps(body), status=status, mimetype="application/json")

def _now_stamp():
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")

def _try_push(entry):
    """Attempt a synchronous ES push for a completed entry.

    Returns True on success, False on any failure (unhealthy cluster, push
    returned false, or an exception). Callers use the boolean to decide
    between mark_flushed + 201 and "leave in pending_flush" + 202.
    """
    es = _es()
    try:
        if not es.health_check():
            return False
        return bool(es.push(entry, "create"))
    except Exception:
        logger.exception("Synchronous push raised; entry will be retried by flusher")
        return False


def _validate_completed(entry):
    """Run the completed entry through Payload.validate_schema like every
    other producer. Returns the normalised dict or raises ValueError."""
    p = Payload(json.dumps(entry))
    p.validate_schema()
    return dict(p.data)


@timers_bp.route("", methods=["POST"])
def start_timer():
    body = request.get_json(silent=True)
    if body is None:
        body = {}
    if not isinstance(body, dict):
        return Response("Malformed or missing JSON body", 400)

    start_str = body.get("start")
    start_dt = None
    if start_str:
        try:
            start_dt = datetime.fromisoformat(str(start_str).replace("Z", "+00:00"))
        except ValueError:
            return Response("'start' must be an ISO 8601 timestamp", 400)
        if start_dt.tzinfo is None:
            return Response("'start' must include a timezone offset", 400)

    try:
        result = _store().start(
            description=body.get("description"),
            project=body.get("project"),
            project_id=body.get("projectId"),
            task=body.get("task"),
            start=start_dt,
        )
    except ConflictError as exc:
        # The atomic auto-stop in start() should make this unreachable in
        # practice, but if the invariant is ever violated we explicitly raise
        # a 409 rather than a 500.
        logger.error("Timer start conflict: %s", exc)
        return Response(str(exc), 409)

    stopped = result["stopped"]
    if stopped is not None:
        # A prior running timer was auto-stopped. Try to push it right now
        # for lower latency; if it fails, the flusher already has a claim on
        # the row (next_retry_at was set in the same transaction).
        try:
            validated = _validate_completed(stopped)
        except (ValueError, TypeError) as exc:
            # Very unlikely as we constructed the entry ourselves, but if
            # validation fails we leave the row in pending_flush for inspection
            # rather than silently pushing bad data.
            logger.error("Auto-stopped entry failed validation: %s", exc)
        else:
            validated["@timestamp"] = _now_stamp()
            if _try_push(validated):
                _store().mark_flushed(stopped["id"])

    logger.info("Started timer %s", result["started"]["id"])
    return _json({"started": result["started"], "stopped": stopped}, 201)


@timers_bp.route("", methods=["GET"])
def get_running():
    running = _store().get_running()
    if running is None:
        return Response("", status=204)
    return _json(running, 200)


@timers_bp.route("/<timer_id>/stop", methods=["POST"])
def stop_timer(timer_id):
    try:
        entry = _store().stop(timer_id)
    except NotFoundError as exc:
        return Response(str(exc), 404)

    try:
        validated = _validate_completed(entry)
    except (ValueError, TypeError) as exc:
        # We built the entry from a validated running row plus a computed
        # end/duration, so validation should not fail here. If it does the
        # row is already in pending_flush and we return 500 rather than
        # attempt a push we know is unsound.
        logger.error("Stop for %s produced invalid entry: %s", timer_id, exc)
        return Response(f"Internal error: invalid entry: {exc}", 500)

    validated["@timestamp"] = _now_stamp()

    if _try_push(validated):
        _store().mark_flushed(timer_id)
        logger.info("Stopped and pushed timer %s", timer_id)
        return _json(validated, 201)

    # The synchronous push didn't succeed. The row is still in pending_flush
    # so the flusher will retry. From the user's perspective the timer is
    # stopped, just not yet visible in the dashboard.
    logger.info("Stopped timer %s; queued for flusher retry", timer_id)
    return _json(
        {"id": timer_id, "status": "pending_flush", "entry": validated},
        202,
    )


@timers_bp.route("/<timer_id>", methods=["DELETE"])
def cancel_timer(timer_id):
    if _store().cancel(timer_id):
        logger.info("Cancelled timer %s", timer_id)
        return Response("", status=204)
    return Response("No running timer with that id", 404)
