"""Tests for the auth blueprint and the global auth+CSRF before_request.

Auth is opt-in on the app: with no ACCESS_TOKEN configured, everything
is open (see test_lookup_routes.py which relies on this). These tests
enable auth via the `authed_app` fixture to exercise the gated paths.
"""
import re
import pytest


TEST_TOKEN = "correct-horse-battery-staple"


@pytest.fixture
def authed_app(app):
    original = app.config.get("ACCESS_TOKEN")
    app.config["ACCESS_TOKEN"] = TEST_TOKEN
    yield app
    app.config["ACCESS_TOKEN"] = original


@pytest.fixture
def authed_client(authed_app):
    return authed_app.test_client()


def _csrf_from(body):
    """Extract a CSRF token from either the login form or the meta tag."""
    m = re.search(r'name="csrf_token" value="([^"]+)"', body)
    if m:
        return m.group(1)
    m = re.search(r'name="csrf-token" content="([^"]+)"', body)
    return m.group(1) if m else None


def _login(client, token=TEST_TOKEN):
    """Complete the GET+POST login dance. Returns the post-login CSRF token
    (rotated on successful auth) for use with subsequent state-changing calls."""
    r = client.get("/login")
    assert r.status_code == 200
    pre_csrf = _csrf_from(r.data.decode())
    assert pre_csrf, "no CSRF in login form"

    r = client.post("/login", data={
        "password": token, "csrf_token": pre_csrf, "next": "/",
    })
    assert r.status_code in (302, 303), f"login failed: {r.status_code}"

    # Post-login the CSRF was rotated; grab the new one from the SPA meta tag.
    r = client.get("/")
    assert r.status_code == 200
    post_csrf = _csrf_from(r.data.decode())
    assert post_csrf, "no CSRF meta on index"
    return post_csrf


class TestAuthGate:
    def test_api_returns_401_without_session(self, authed_client):
        r = authed_client.get("/api/clients")
        assert r.status_code == 401

    def test_html_redirects_to_login(self, authed_client):
        r = authed_client.get("/")
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_ping_stays_open(self, authed_client):
        r = authed_client.get("/ping")
        assert r.status_code == 200

    def test_webhook_bypasses_global_auth(self, authed_client):
        # Webhook has its own signature check; the global gate must not
        # short-circuit it with a 401 before that runs.
        r = authed_client.post("/webhook/clockify", json={})
        assert r.status_code != 401


class TestLoginForm:
    def test_get_renders_form_with_csrf(self, authed_client):
        r = authed_client.get("/login")
        assert r.status_code == 200
        assert b"password" in r.data.lower()
        assert _csrf_from(r.data.decode()) is not None

    def test_wrong_password_401(self, authed_client):
        r = authed_client.get("/login")
        csrf = _csrf_from(r.data.decode())
        r = authed_client.post("/login", data={"password": "wrong", "csrf_token": csrf})
        assert r.status_code == 401

    def test_missing_csrf_on_login_403(self, authed_client):
        # No prior GET, so the session has no CSRF token to match against
        r = authed_client.post("/login", data={"password": TEST_TOKEN})
        assert r.status_code == 403

    def test_open_redirect_defended(self, authed_client):
        r = authed_client.get("/login")
        csrf = _csrf_from(r.data.decode())
        r = authed_client.post("/login", data={
            "password": TEST_TOKEN, "csrf_token": csrf,
            "next": "https://evil.example.com/steal",
        })
        assert r.status_code in (302, 303)
        # Redirect target normalises to "/" rather than the external URL
        assert r.headers["Location"] in ("/", "http://localhost/")


class TestPostLoginAccess:
    def test_api_accessible_after_login(self, authed_client, es_mock):
        es_mock.distinct_clients.return_value = []
        _login(authed_client)
        r = authed_client.get("/api/clients")
        assert r.status_code == 200

    def test_index_renders_after_login(self, authed_client):
        _login(authed_client)
        r = authed_client.get("/")
        assert r.status_code == 200
        assert b"Clockbridge" in r.data


class TestCsrfOnStateChangingApi:
    def test_post_without_csrf_header_403(self, authed_client, es_mock):
        _login(authed_client)
        r = authed_client.post("/api/entries", json={"start": "x", "end": "y"})
        assert r.status_code == 403

    def test_post_with_wrong_csrf_403(self, authed_client, es_mock):
        _login(authed_client)
        r = authed_client.post(
            "/api/entries", json={"start": "x", "end": "y"},
            headers={"X-CSRF-Token": "not-the-token"},
        )
        assert r.status_code == 403

    def test_post_with_valid_csrf_passes_gate(self, authed_client, es_mock):
        # We only care that CSRF didn't block; the entry body is bad, so
        # the route will 400, but that means we got past the gate.
        csrf = _login(authed_client)
        r = authed_client.post(
            "/api/entries", json={"start": "x", "end": "y"},
            headers={"X-CSRF-Token": csrf},
        )
        assert r.status_code not in (401, 403)


class TestLogout:
    def test_logout_clears_session(self, authed_client, es_mock):
        es_mock.distinct_clients.return_value = []
        csrf = _login(authed_client)
        r = authed_client.post("/logout", headers={"X-CSRF-Token": csrf})
        assert r.status_code in (302, 303)
        # Session cleared: next API call requires re-login
        r = authed_client.get("/api/clients")
        assert r.status_code == 401


class TestDynamicSecureCookie:
    """The custom session interface sets the Secure cookie flag based on the
    request's actual scheme (via ProxyFix's X-Forwarded-Proto handling in
    prod). This lets the same instance serve HTTPS externally and HTTP on
    a trusted internal network without either path breaking."""

    def test_http_request_gets_non_secure_cookie(self, authed_client):
        r = authed_client.get("/login")
        set_cookie = r.headers.get("Set-Cookie", "")
        assert "session=" in set_cookie
        assert "Secure" not in set_cookie

    def test_https_request_gets_secure_cookie(self, authed_client):
        r = authed_client.get("/login", base_url="https://localhost")
        set_cookie = r.headers.get("Set-Cookie", "")
        assert "session=" in set_cookie
        assert "Secure" in set_cookie
