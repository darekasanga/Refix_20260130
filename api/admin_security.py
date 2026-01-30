"""
Security helpers for admin authentication and secret storage.
"""

from __future__ import annotations

import base64
import hashlib
import os

import bcrypt
from cryptography.fernet import Fernet


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _derive_fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet() -> Fernet:
    secret = os.environ.get("WIFI_LOCAL_SECRET_KEY") or os.environ.get(
        "SESSION_SECRET", "dev-wifi-secret"
    )
    return Fernet(_derive_fernet_key(secret))


def encrypt_secret(raw: str) -> str:
    return get_fernet().encrypt(raw.encode("utf-8")).decode("utf-8")


def decrypt_secret(payload: str) -> str:
    return get_fernet().decrypt(payload.encode("utf-8")).decode("utf-8")
