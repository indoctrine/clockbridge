"""
AUTHOR:     Beck D.
DATE:       2026-
PURPOSE:    Authentication and CSRF protection.

Auth is opt-in: with `access_token` unset in config (and no
CLOCKBRIDGE_ACCESS_TOKEN env var), the app runs open and logs a warning
at startup. This preserves existing behaviour for local dev and tests.

When enabled, the flow is:
    GET  /login   -> render form with a per-session CSRF token
    POST /login   -> verify CSRF and access_token (constant-time), rotate
                     session on success, redirect to `next`
    POST /logout  -> clear session

The signed session cookie (Flask's built-in itsdangerous machinery) is
HttpOnly + SameSite=Lax + Secure. Lax blocks the cross-site POST vector
for CSRF; the per-session CSRF token is defence in depth against browser
quirks and mishandled edge cases. Both must pass for state-changing
requests to succeed.
"""

import hmac
import secrets
import logging
from flask import (
    Blueprint, current_app, redirect, render_template, request,
    Response, session, url_for,
)

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


def ensure_csrf_token():
    """Return the current session's CSRF token, creating one if absent.
    Called from a Jinja context processor so templates can render it."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def _wants_json():
    return (
        request.path.startswith("/api/")
        or request.accept_mimetypes.best == "application/json"
    )


def _is_local_path(path):
    # Guards against open-redirect via ?next=https://evil.example.com
    return isinstance(path, str) and path.startswith("/") and not path.startswith("//")


# Endpoints and paths that bypass the auth+CSRF gate. Webhook has its own
# HMAC signature check; login/logout obviously can't require prior auth;
# static files and ping are harmless.
_EXEMPT_ENDPOINTS = frozenset({
    "auth.login_form", "auth.login", "auth.logout", "static", "ping", "robots",
})
_EXEMPT_PATHS = frozenset({"/webhook/clockify"})


def enforce_auth_and_csrf():
    """Global before_request hook: gates every non-exempt route."""
    endpoint = request.endpoint or ""
    if endpoint in _EXEMPT_ENDPOINTS or request.path in _EXEMPT_PATHS:
        return None

    token_configured = bool(current_app.config.get("ACCESS_TOKEN"))
    if not token_configured:
        return None  # Auth disabled globally

    if not session.get("authenticated"):
        if _wants_json():
            return Response("Unauthorized", 401)
        return redirect(url_for("auth.login_form", next=request.full_path.rstrip("?")))

    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        submitted = request.headers.get("X-CSRF-Token")
        if not submitted and request.form:
            submitted = request.form.get("csrf_token")
        expected = session.get("csrf_token", "")
        if (not submitted or not expected
                or not hmac.compare_digest(submitted, expected)):
            return Response("CSRF token missing or invalid", 403)
    return None


@auth_bp.route("/login", methods=["GET"])
def login_form():
    ensure_csrf_token()
    return render_template("login.html",
                           next=request.args.get("next", "/"),
                           error=None)


@auth_bp.route("/login", methods=["POST"])
def login():
    expected = current_app.config.get("ACCESS_TOKEN", "")
    if not expected:
        return Response("Auth is disabled on this server", 400)

    # Pre-login CSRF: the token came from the GET that rendered the form,
    # so a cross-site POST can't populate it correctly.
    ensure_csrf_token()
    submitted_csrf = request.form.get("csrf_token", "")
    if not hmac.compare_digest(submitted_csrf, session.get("csrf_token", "")):
        return Response("CSRF token missing or invalid", 403)

    submitted = request.form.get("password", "")
    if not hmac.compare_digest(submitted, expected):
        logger.info("Failed login from %s", request.remote_addr)
        return render_template("login.html",
                               next=request.form.get("next", "/"),
                               error="Invalid token"), 401

    # Session fixation defence: wipe the pre-auth session and reissue a
    # fresh CSRF token bound to the newly authenticated session.
    session.clear()
    session["authenticated"] = True
    session["csrf_token"] = secrets.token_urlsafe(32)
    session.permanent = True

    target = request.form.get("next", "/")
    if not _is_local_path(target):
        target = "/"
    return redirect(target)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login_form"))
