import sys
import os
from clockbridgeconfig import Config
sys.path.append(os.path.abspath('../'))

config_path = os.path.join(os.getcwd(), "tests/testConfig.yaml")

class TestRoutes:
    """Test expected results from various methods and routes"""
    def setup_class(self):
        self.config = Config(config_path)

    def test_invalid_route(self, app, client):
        """ Test an invalid route returns 404 """
        res = client.get('/')
        expected = 404
        assert res.status_code == expected

    def test_valid_route_invalid_method(self, app, client):
        """ Test an valid route with an invalid method returns 405 """
        res = client.get('/webhook/clockify')
        expected = 405
        assert res.status_code == expected

    def test_valid_route_malformed_body(self, app,client):
        """ Test valid route with malformed body returns 403 """
        res = client.post('/webhook/clockify', data="testingtesting")
        expected = 403
        assert res.status_code == expected
