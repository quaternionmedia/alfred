# import pytest

from alfred.main import app
from fastapi.testclient import TestClient


client = TestClient(app)


def test_get_index():
    """Check response from / is html"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"


def test_login_fail():
    """Test login fail"""
    response = client.post(
        "/auth/login",
        json={"username": "test", "password": "test"},
    )
    assert response.status_code == 405
    message = response.json()
    assert message.get('detail') == 'Method Not Allowed'
