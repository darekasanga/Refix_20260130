"""
Security helpers for hashing and verifying management codes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Tuple

PBKDF2_ITERATIONS = 200_000


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


def hash_code(code: str) -> Tuple[str, str]:
    """
    Return a tuple of (salt_b64, hash_b64) using PBKDF2-HMAC-SHA256.
    A per-code salt is used to defend against rainbow table attacks.
    """
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return _b64encode(salt), _b64encode(digest)


def verify_code(code: str, salt_b64: str, hash_b64: str) -> bool:
    """Check whether the provided code matches the stored hash."""
    salt = _b64decode(salt_b64)
    expected = _b64decode(hash_b64)
    computed = hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return hmac.compare_digest(expected, computed)


def fingerprint(code: str) -> str:
    """
    A deterministic SHA256 fingerprint used solely to enforce uniqueness
    without persisting the raw code.
    """
    return hashlib.sha256(code.encode("utf-8")).hexdigest()
