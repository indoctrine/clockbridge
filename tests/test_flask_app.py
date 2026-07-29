import sys
import os
from clockbridgeconfig import Config
sys.path.append(os.path.abspath('../'))

config_path = os.path.join(os.getcwd(), "tests/testConfig.yaml")

class TestRoutes:
    """Test expected results from various methods and routes"""
    def setup_class(self):
        self.config = Config(config_path)

    def test_index_route(self, app, client):
        """ Test the index route renders the SPA shell """
        res = client.get('/')
        assert res.status_code == 200
        assert b"Clockbridge" in res.data

    def test_invalid_route(self, app, client):
        """ Test an unknown route returns 404 """
        res = client.get('/nope')
        assert res.status_code == 404

    def test_valid_route_invalid_method(self, app, client):
        """ Test an valid route with an invalid method returns 405 """
        res = client.get('/webhook/clockify')
        expected = 405
        assert res.status_code == expected

    def test_valid_route_malformed_body(self, app, client):
        """ Test valid route with malformed body returns 415 """
        res = client.post('/webhook/clockify', data="testingtesting")
        expected = 415
        assert res.status_code == expected


class TestRobotsExclusion:
    def test_robots_txt_disallows_everything(self, client):
        r = client.get("/robots.txt")
        assert r.status_code == 200
        assert r.mimetype == "text/plain"
        assert b"User-agent: *" in r.data
        assert b"Disallow: /" in r.data

    def test_x_robots_tag_on_index(self, client):
        r = client.get("/")
        assert "noindex" in r.headers.get("X-Robots-Tag", "")

    def test_x_robots_tag_on_api(self, client):
        r = client.get("/ping")
        assert "noindex" in r.headers.get("X-Robots-Tag", "")
