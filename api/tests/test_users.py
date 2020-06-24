from .. import users

def test_read_users_me():
    assert users.read_users_me()
