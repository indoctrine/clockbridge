"""
AUTHOR:     Beck D.
DATE:       2023-
PURPOSE:    The main Flask application file
"""

import os
import sys
import hashlib
import logging
import json
import time
import uuid
from datetime import datetime, timedelta
from queue import Queue
from flask import Flask, Response, render_template, request, send_from_directory
from flask.sessions import SecureCookieSessionInterface
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from timer_store import TimerStore
from timers import timers_bp
from flusher import Flusher
from elastic import Elastic
from payload import Payload
import webhook
from clockbridgeconfig import Config
from auth import auth_bp, enforce_auth_and_csrf, ensure_csrf_token

file_path = os.environ.get('CLOCKBRIDGE_CONFIG_PATH')
if not file_path:
    file_path = os.path.join(os.getcwd(), 'config.yaml')

app = Flask(__name__)
config = Config(file_path)
logging.info("Configuration loaded from %s, logging at %s level", file_path, config.log_level)
job_queue = Queue(maxsize=100)
es = Elastic(config.elastic_creds)

# Timer state store + retry loop. The store is shared across gunicorn workers
# via the SQLite file at config.sqlite_path; each worker gets its own Flusher
# thread, and TimerStore.claim_due is atomic so a given pending_flush row is
# handed to exactly one worker per tick.
timer_store = TimerStore(config.sqlite_path)
app.config["TIMER_STORE"] = timer_store
app.config["ES"] = es
app.register_blueprint(timers_bp)

flusher = Flusher(timer_store, es)

if not os.environ.get("CLOCKBRIDGE_DISABLE_FLUSHER"):
    flusher.start()

logging.Formatter.converter = time.localtime
logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    stream=sys.stderr)
logger.setLevel(config.log_level)

# ---- auth, session, CSRF, rate limiting --------------------------------

access_token = getattr(config, "access_token", None)
app.config["ACCESS_TOKEN"] = access_token

if access_token:
    # Derive the session signing key from the token: rotating the token
    # automatically invalidates every session cookie previously issued.
    app.config["SECRET_KEY"] = hashlib.sha256(access_token.encode()).digest()
else:
    # Random per-process key so sessions still work locally, but you get a
    # loud warning that anyone hitting this instance can drive it.
    app.config["SECRET_KEY"] = os.urandom(32)
    logger.warning(
        "access_token is not set in config (or CLOCKBRIDGE_ACCESS_TOKEN); "
        "auth is DISABLED. Do NOT expose this instance to the internet."
    )

# Application is proxy-aware and cookies will have Same-Site: Secure flag when 
# accessed via the reverse proxy (i.e. externally from the internet) with Lax 
# used when accessed internally (no https).
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)


class RequestAwareSessionInterface(SecureCookieSessionInterface):
    """Flip the `Secure` cookie flag based on the current request's scheme
    rather than a static config value. Combined with ProxyFix reading
    X-Forwarded-Proto from a trusted reverse proxy, this lets one deployment
    serve both HTTPS-through-proxy and direct HTTP on the LAN without either
    breaking. Falls back to the config value when there's no request context
    (e.g. during startup or a shell)."""

    def get_cookie_secure(self, app):
        try:
            return request.is_secure
        except RuntimeError:
            return app.config.get("SESSION_COOKIE_SECURE", True)


app.session_interface = RequestAwareSessionInterface()

# If a reverse proxy sits in front, tell Flask to honour its X-Forwarded-Proto
# (and X-Forwarded-For for accurate rate-limit keys). Only enable this when
# you actually have a proxy in front: with it enabled and no proxy, an
# attacker could set the header themselves. Your proxy MUST strip any
# incoming X-Forwarded-* from clients and set its own - nginx, Traefik, and
# Caddy all do this by default; double-check if you're on something exotic.
if os.environ.get("CLOCKBRIDGE_TRUST_PROXY") == "1":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

app.register_blueprint(auth_bp)
app.before_request(enforce_auth_and_csrf)

@app.context_processor
def _inject_csrf():
    return {"csrf_token": ensure_csrf_token}

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["300 per minute"],
    storage_uri="memory://",
)
# Applies to all endpoints in the auth blueprint (login GET/POST, logout).
limiter.limit("10 per minute")(auth_bp)


# Maps Clockify webhook event types to the generic action verbs understood by
# Elastic.push(). Anything not listed here (NEW_TIME_ENTRY, TIMER_STOPPED, ...)
# is treated as a create.
CLOCKIFY_ACTION_MAP = {
    "TIME_ENTRY_DELETED": "delete",
    "TIME_ENTRY_UPDATED": "update",
}

@app.route("/ping", methods = ['GET'])
def ping():
    return "Pong\n"

@app.route("/robots.txt", methods=["GET"])
def robots():
    return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")

@app.after_request
def _no_robots(response):
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response

@app.route("/webhook/clockify", methods = ['POST'])
def clockbridge():
    try:
        logger.info("Incoming payload")
        hook = webhook.Webhook(config)
        logger.debug("Payload received with headers:\n %s", dict(request.headers))
        logger.debug("Payload contents:\n %s", json.dumps(request.json, indent=4))
        if request.json['timeInterval']['end'] is None:
            return Response("Payload not ready for upload", 409)

        payload = hook.verify_incoming_webhook(request)
        if not payload:
            return Response("Unauthorized", 403)

        now = datetime.now().astimezone()
        payload['@timestamp'] = now.strftime('%Y-%m-%dT%H:%M:%S%z')
        job_queue.put(payload)

    except ValueError:
        return Response("Malformed request body", 400)

    try:
        if es.health_check():
            logger.info("Elasticsearch endpoint up, pushing data...")
            for job in range(job_queue.qsize()):
                data = job_queue.get(job)
                verb = CLOCKIFY_ACTION_MAP.get((hook.action or "").upper(), "create")
                r = es.push(data, verb)

                if not r:
                    # If the task above doesn't complete successfully, put the job back in the queue
                    job_queue.put(data)
            return Response("Data successfully inserted into Elasticsearch", 200)
    except Exception:
        return Response(503)

def build_entry(body):
    """Build an entry dict from frontend input.

    Used by non-Clockify entries. Creates a custom document id and computes 
    duration server-side from start/end with client-supplied duration being ignored. 
    The optional fields are included explicitly as None because the schema treats them as 
    required-but-nullable.
    
    Raises ValueError on missing/invalid input; full schema validation and
    date/duration normalisation happen downstream in Payload.validate_schema().
    """
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")

    start = body.get("start")
    end = body.get("end")
    if not start or not end:
        raise ValueError("Both 'start' and 'end' are required")

    try:
        start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("'start' and 'end' must be ISO 8601 timestamps") from exc

    if end_dt <= start_dt:
        raise ValueError("'end' must be after 'start'")

    return {
        "id": str(uuid.uuid4()),
        "description": body.get("description"),
        "project": body.get("project"),
        "projectId": body.get("projectId"),
        "task": body.get("task"),
        "timeInterval": {
            "start": start,
            "end": end,
            "duration": int((end_dt - start_dt).total_seconds()),
        },
    }

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route("/api/entries", methods = ['POST'])
def create_entry():
    """Create a completed time entry from the frontend (manual entry / timer stop).

    On an Elasticsearch failure it returns an error so the caller can retry,
    rather than enqueuing onto the per-worker webhook queue.
    """
    body = request.get_json(silent=True)
    if body is None:
        return Response("Malformed or missing JSON body", 400)

    try:
        entry = build_entry(body)
        payload = Payload(json.dumps(entry))
        payload.validate_schema()
        validated = dict(payload.data)
    except (ValueError, TypeError) as exc:
        logger.info("Rejected manual entry: %s", exc)
        return Response(f"Invalid entry: {exc}", 400)

    now = datetime.now().astimezone()
    validated['@timestamp'] = now.strftime('%Y-%m-%dT%H:%M:%S%z')

    try:
        if not es.health_check():
            return Response("Elasticsearch unavailable", 503)
        if not es.push(validated, "create"):
            return Response("Failed to insert entry into Elasticsearch", 502)
    except Exception:
        logger.exception("Error pushing manual entry to Elasticsearch")
        return Response("Elasticsearch unavailable", 503)

    logger.info("Created manual entry %s", validated["id"])
    return Response(json.dumps({"id": validated["id"]}),
                    status=201, mimetype="application/json")

def _json_response(body, status=200):
    return Response(json.dumps(body, default=str),
                    status=status, mimetype="application/json")

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/api/clients", methods=["GET"])
def list_clients():
    try:
        return _json_response(es.distinct_clients())
    except Exception:
        logger.exception("Failed listing clients")
        return Response("Elasticsearch unavailable", 503)

@app.route("/api/projects", methods=["GET"])
def list_projects():
    try:
        return _json_response(es.distinct_projects(request.args.get("client")))
    except Exception:
        logger.exception("Failed listing projects")
        return Response("Elasticsearch unavailable", 503)

@app.route("/api/tasks", methods=["GET"])
def list_tasks():
    try:
        return _json_response(es.distinct_tasks(request.args.get("project")))
    except Exception:
        logger.exception("Failed listing tasks")
        return Response("Elasticsearch unavailable", 503)

@app.route("/api/entries/recent", methods=["GET"])
def list_recent_entries():
    try:
        limit = max(1, min(int(request.args.get("limit", 10)), 100))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        return Response("limit and offset must be integers", 400)
    try:
        return _json_response(es.recent_entries(limit, offset))
    except Exception:
        logger.exception("Failed listing recent entries")
        return Response("Elasticsearch unavailable", 503)

if __name__ == "__main__":
    app.run(debug=True, port=5000, host='0.0.0.0')
