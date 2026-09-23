import os

def test_password_round_trip(tmp_path,monkeypatch):
    monkeypatch.setenv('JWT_SECRET','test-secret')
    from app.security import password_hash,password_verify
    stored=password_hash('a-very-long-password')
    assert password_verify('a-very-long-password',stored)
    assert not password_verify('wrong-password',stored)
