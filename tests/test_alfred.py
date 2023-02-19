# import pytest

from fastapi.testclient import TestClient
from alfred.main import app

client = TestClient(app)


# @pytest.mark.parametrize(
#     "route, response_code, response",
#     [
#         ("/", 200, ),
#         ("/users/me", 401, {"detail": "Not authenticated"}),

#     ],
# )
# def test_get_routes(route, response_code, response):
#     response = client.get(route)
#     assert response.status_code == response_code
#     assert response.json() == response


# test response from / is html
def test_get_index():
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"


# test login fail
def test_login_fail():
    response = client.post(
        "/auth/login",
        json={"username": "test", "password": "test"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}


# @pytest.mark.parametrize(
#     "phrase, expected",
#     [
#         ("test", "test"),
#         ("1 2 1 2", "1 2 1 2"),
#         ("\n", "\n"),
#     ],
# )
# def test_parse_input(phrase, expected):
#     assert parse_input(phrase) == expected
