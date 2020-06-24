from .db import db

def test_db():
    assert db.name == 'alfred'
