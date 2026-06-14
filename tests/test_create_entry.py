"""Tests for the /api/entries manual-entry route and Elastic.push() method."""
import sys
import os
import app as app_module
from elastic import Elastic

sys.path.append(os.path.abspath('../'))


class TestCreateEntryRoute:
    """Test the manual-entry endpoint end to end with Elasticsearch mocked."""

    def _valid_body(self):
        return {
            "description": "Test",
            "start": "2024-06-11T13:02:00Z",
            "end": "2024-06-11T13:59:00Z",
        }

    def test_valid_entry_is_created(self, client, monkeypatch):
        """A valid body returns 201, a generated id, and pushes a normalised entry."""
        captured = {}

        def fake_push(data, action="create"):
            captured["data"] = data
            captured["action"] = action
            return True

        monkeypatch.setattr(app_module.es, "health_check", lambda: True)
        monkeypatch.setattr(app_module.es, "push", fake_push)

        res = client.post("/api/entries", json=self._valid_body())
        assert res.status_code == 201

        returned_id = res.get_json()["id"]
        pushed = captured["data"]
        assert captured["action"] == "create"
        assert pushed["id"] == returned_id            # id is minted and echoed back
        assert pushed["timeInterval"]["duration"] == 3420   # 57 mins, computed server-side
        assert pushed["timeInterval"]["start"] == "2024-06-11T13:02:00+0000"  # normalised
        assert "@timestamp" in pushed                 # stamped like the webhook path

    def test_missing_times_rejected(self, client, monkeypatch):
        """Missing start/end is a 400 and never reaches Elasticsearch."""
        monkeypatch.setattr(app_module.es, "health_check", lambda: True)
        monkeypatch.setattr(app_module.es, "push",
                            lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not push")))
        res = client.post("/api/entries", json={"description": "no times"})
        assert res.status_code == 400

    def test_end_before_start_rejected(self, client, monkeypatch):
        """An end at or before start is a 400."""
        monkeypatch.setattr(app_module.es, "health_check", lambda: True)
        body = {"start": "2024-06-11T14:00:00Z", "end": "2024-06-11T13:00:00Z"}
        res = client.post("/api/entries", json=body)
        assert res.status_code == 400

    def test_non_json_body_rejected(self, client):
        """A non-JSON body is a 400 rather than a 500."""
        res = client.post("/api/entries", data="not json")
        assert res.status_code == 400

    def test_elasticsearch_down_returns_503(self, client, monkeypatch):
        """If the cluster health check fails, the caller gets a 503 to retry."""
        monkeypatch.setattr(app_module.es, "health_check", lambda: False)
        res = client.post("/api/entries", json=self._valid_body())
        assert res.status_code == 503


class TestPushDispatch:
    """Test that Elastic.push() routes to the correct method per action verb."""

    def _elastic(self):
        return Elastic({
            "url": "https://test.com:9200/", "index_prefix": "test",
            "username": "u", "password": b"p", "insecure": True,
        })

    def test_dispatch(self, monkeypatch):
        es = self._elastic()
        calls = []
        monkeypatch.setattr(es, "create_doc", lambda d: calls.append("create") or True)
        monkeypatch.setattr(es, "update_doc", lambda d: calls.append("update") or True)
        monkeypatch.setattr(es, "delete_doc", lambda d: calls.append("delete") or True)

        es.push({}, "create")
        es.push({}, "update")
        es.push({}, "delete")
        es.push({}, "anything-else")   # unknown -> create
        assert calls == ["create", "update", "delete", "create"]
