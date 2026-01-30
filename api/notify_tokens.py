"""
Token helpers for notification QR codes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _base64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def generate_notify_token(
    *,
    token_id: str,
    thread_id: str,
    child_id: str,
    ttl_seconds: int,
    secret: str,
) -> str:
    payload = {
        "token_id": token_id,
        "thread_id": thread_id,
        "child_id": child_id,
        "exp": int(time.time()) + ttl_seconds,
    }
    payload_b64 = _base64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return f"{payload_b64}.{_base64url(signature)}"


def verify_notify_token(token: str, *, secret: str) -> dict[str, Any]:
    try:
        payload_b64, sig_b64 = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid token format") from exc
    expected_sig = hmac.new(
        secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256
    ).digest()
    if not hmac.compare_digest(_base64url(expected_sig), sig_b64):
        raise ValueError("Invalid token signature")
    payload = json.loads(_base64url_decode(payload_b64))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Token expired")
    if not payload.get("token_id") or not payload.get("thread_id") or not payload.get("child_id"):
        raise ValueError("Missing token claims")
    return payload
