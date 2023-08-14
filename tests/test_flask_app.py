import json

def test_invalid_route(app, client):
    """ Test an invalid route returns 404 """
    res = client.get('/')
    expected = 404
    assert res.status_code == expected

def test_valid_route_invalid_method(app, client):
    """ Test an valid route with an invalid method returns 405 """
    res = client.get('/webhook/clockify')
    expected = 405
    assert res.status_code == expected

def test_valid_route_malformed_body(app,client):
    """ Test valid route with malformed body returns 400 """
    res = client.post('/webhook/clockify', data="testingtesting")
    expected = 400
    assert res.status_code == expected
