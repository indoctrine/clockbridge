"""Tests for the frontend-facing lookup endpoints (clients/projects/tasks/recent)."""
import json


class TestClientsRoute:
    def test_returns_distinct_clients(self, client, es_mock):
        es_mock.distinct_clients.return_value = [
            {"clientId": "c1", "clientName": "Drawing"},
            {"clientId": "c2", "clientName": "Drumming"},
        ]
        res = client.get("/api/clients")
        assert res.status_code == 200
        assert json.loads(res.data) == [
            {"clientId": "c1", "clientName": "Drawing"},
            {"clientId": "c2", "clientName": "Drumming"},
        ]

    def test_returns_503_when_es_raises(self, client, es_mock):
        es_mock.distinct_clients.side_effect = RuntimeError("boom")
        res = client.get("/api/clients")
        assert res.status_code == 503


class TestProjectsRoute:
    def test_no_client_filter(self, client, es_mock):
        es_mock.distinct_projects.return_value = []
        res = client.get("/api/projects")
        assert res.status_code == 200
        es_mock.distinct_projects.assert_called_once_with(None)

    def test_with_client_filter(self, client, es_mock):
        es_mock.distinct_projects.return_value = [
            {"projectId": "p1", "name": "Studies",
             "clientId": "c1", "clientName": "Drawing"},
        ]
        res = client.get("/api/projects?client=c1")
        assert res.status_code == 200
        es_mock.distinct_projects.assert_called_once_with("c1")
        assert json.loads(res.data)[0]["projectId"] == "p1"


class TestTasksRoute:
    def test_no_project_filter(self, client, es_mock):
        es_mock.distinct_tasks.return_value = []
        res = client.get("/api/tasks")
        assert res.status_code == 200
        es_mock.distinct_tasks.assert_called_once_with(None)

    def test_with_project_filter(self, client, es_mock):
        es_mock.distinct_tasks.return_value = [{"name": "Miniatures"}]
        res = client.get("/api/tasks?project=p1")
        assert res.status_code == 200
        es_mock.distinct_tasks.assert_called_once_with("p1")
        assert json.loads(res.data) == [{"name": "Miniatures"}]


class TestRecentEntriesRoute:
    def test_defaults(self, client, es_mock):
        es_mock.recent_entries.return_value = []
        res = client.get("/api/entries/recent")
        assert res.status_code == 200
        es_mock.recent_entries.assert_called_once_with(10, 0)

    def test_custom_pagination(self, client, es_mock):
        es_mock.recent_entries.return_value = []
        res = client.get("/api/entries/recent?limit=25&offset=50")
        assert res.status_code == 200
        es_mock.recent_entries.assert_called_once_with(25, 50)

    def test_limit_clamped(self, client, es_mock):
        es_mock.recent_entries.return_value = []
        client.get("/api/entries/recent?limit=999")
        es_mock.recent_entries.assert_called_once_with(100, 0)

    def test_bad_limit_returns_400(self, client, es_mock):
        res = client.get("/api/entries/recent?limit=abc")
        assert res.status_code == 400

    def test_returns_503_when_es_raises(self, client, es_mock):
        es_mock.recent_entries.side_effect = RuntimeError("boom")
        res = client.get("/api/entries/recent")
        assert res.status_code == 503
