from .. import auth

from hypothesis import given
from hypothesis.strategies import text




def test_key():
    assert auth.SECRET_KEY

def test_get_current_user():
    assert auth.get_current_user()

def test_get_current_active_user():
    assert auth.get_current_active_user()

@given(text())
def test_get_password_hash(p):
    assert auth.get_password_hash(p)

@given(text())
def test_verify_password(p):
    assert auth.verify_password(p, auth.get_password_hash(p))
