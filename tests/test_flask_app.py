import json

def test_invalid_route(app, client):
    res = client.get('/')
    expected = 404
    assert res.status_code == expected

def test_valid_route_invalid_method(app, client):
    res = client.get('/webhook/clockify')
    expected = 405
    assert res.status_code == expected

def test_valid_route_malformed_body(app,client):
    res = client.post('/webhook/clockify', data="testingtesting")
    expected = 400
    assert res.status_code == expected