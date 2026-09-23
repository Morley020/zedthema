"""Small security helpers used by ZedThema.

The goal is to keep the security code easy to understand.  Passwords are never
stored directly.  Sensitive research text can be encrypted before it is saved
in SQLite.  The encryption key is stored separately from the database.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from .config import DATA_DIR, ENCRYPTION_ENABLED, JWT_SECRET

KEY_FILE = DATA_DIR / ".qualicoder.key"


def _key() -> bytes:
    """Create or load the local encryption key."""
    if not KEY_FILE.exists():
        KEY_FILE.write_bytes(Fernet.generate_key())
        try:
            os.chmod(KEY_FILE, 0o600)
        except OSError:
            pass
    return KEY_FILE.read_bytes().strip()


def encrypt(value: str | None) -> str | None:
    if value is None:
        return None
    if not ENCRYPTION_ENABLED:
        return value
    return "enc:" + Fernet(_key()).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(value: str | None) -> str | None:
    if value is None:
        return None
    if not value.startswith("enc:"):
        # This makes upgrades from the original starter database possible.
        return value
    if not ENCRYPTION_ENABLED:
        raise RuntimeError("Encrypted data exists but ENCRYPTION_ENABLED=false")
    try:
        return Fernet(_key()).decrypt(value[4:].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Could not decrypt research data. Check the encryption key.") from exc


def password_hash(password: str) -> str:
    """Hash a password with PBKDF2.  No password is stored in plain text."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return base64.urlsafe_b64encode(salt + digest).decode("ascii")


def password_verify(password: str, stored: str) -> bool:
    try:
        raw = base64.urlsafe_b64decode(stored.encode("ascii"))
        salt, expected = raw[:16], raw[16:]
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_token(user_id: str, email: str, role: str = "researcher", ttl_seconds: int = 8 * 3600) -> str:
    """Create a small signed token without adding a large authentication library."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user_id, "email": email, "role": role, "exp": int(time.time()) + ttl_seconds}
    def enc(obj: Any) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj, separators=(",", ":")).encode()).decode().rstrip("=")
    body = f"{enc(header)}.{enc(payload)}"
    sig = hmac.new(JWT_SECRET.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"


def verify_token(token: str) -> dict[str, Any]:
    try:
        header, payload, signature = token.split(".")
        body = f"{header}.{payload}"
        expected = base64.urlsafe_b64encode(hmac.new(JWT_SECRET.encode(), body.encode(), hashlib.sha256).digest()).decode().rstrip("=")
        if not hmac.compare_digest(expected, signature):
            raise ValueError("Invalid signature")
        padded = payload + "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded).decode())
        if int(data["exp"]) < int(time.time()):
            raise ValueError("Token expired")
        return data
    except Exception as exc:
        raise ValueError("Invalid authentication token") from exc
