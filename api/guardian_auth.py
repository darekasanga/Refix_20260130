"""
Authentication helpers for Microsoft 365 guardian login.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any

import jwt
import requests


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _base64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def generate_qr_token(statement_id: str, *, ttl_seconds: int, secret: str) -> str:
    payload = {
        "statement_id": statement_id,
        "exp": int(time.time()) + ttl_seconds,
        "nonce": secrets.token_urlsafe(16),
    }
    payload_b64 = _base64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return f"{payload_b64}.{_base64url(signature)}"


def verify_qr_token(token: str, *, secret: str) -> dict[str, Any]:
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
    if not payload.get("statement_id") or not payload.get("nonce"):
        raise ValueError("Missing token claims")
    return payload


@dataclass
class SessionManager:
    secret: str
    cookie_name: str = "guardian_session"
    max_age_seconds: int = 8 * 60 * 60

    def _sign(self, payload: bytes) -> str:
        return _base64url(hmac.new(self.secret.encode("utf-8"), payload, hashlib.sha256).digest())

    def encode(self, data: dict[str, Any]) -> str:
        now = int(time.time())
        envelope = {"iat": now, "exp": now + self.max_age_seconds, "data": data}
        payload = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
        payload_b64 = _base64url(payload)
        signature = self._sign(payload)
        return f"{payload_b64}.{signature}"

    def decode(self, raw: str | None) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            payload_b64, sig = raw.split(".", 1)
        except ValueError:
            return {}
        expected_sig = self._sign(_base64url_decode(payload_b64))
        if not hmac.compare_digest(expected_sig, sig):
            return {}
        try:
            payload = json.loads(_base64url_decode(payload_b64))
        except json.JSONDecodeError:
            return {}
        if int(payload.get("exp", 0)) < int(time.time()):
            return {}
        return payload.get("data", {})


class M365OIDCClient:
    def __init__(self) -> None:
        self.tenant_id = os.environ.get("M365_TENANT_ID", "common")
        self.client_id = os.environ.get("M365_CLIENT_ID", "")
        self.client_secret = os.environ.get("M365_CLIENT_SECRET", "")
        self.redirect_uri = os.environ.get("M365_REDIRECT_URI", "")
        self._metadata_cache: dict[str, Any] | None = None

    def _metadata(self) -> dict[str, Any]:
        if self._metadata_cache:
            return self._metadata_cache
        url = (
            f"https://login.microsoftonline.com/{self.tenant_id}"
            "/v2.0/.well-known/openid-configuration"
        )
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        self._metadata_cache = res.json()
        return self._metadata_cache

    def authorization_url(self, state: str, *, scope: str = "openid profile email") -> str:
        if not self.client_id or not self.redirect_uri:
            raise ValueError("Missing M365 client configuration")
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "response_mode": "query",
            "scope": scope,
            "state": state,
        }
        query = "&".join(f"{key}={requests.utils.quote(str(val))}" for key, val in params.items())
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize?{query}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        if not self.client_secret:
            raise ValueError("Missing M365 client secret")
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": code,
            "grant_type": "authorization_code",
        }
        res = requests.post(token_url, data=data, timeout=10)
        res.raise_for_status()
        return res.json()

    def verify_id_token(self, id_token: str) -> dict[str, Any]:
        metadata = self._metadata()
        jwks_client = jwt.PyJWKClient(metadata["jwks_uri"])
        signing_key = jwks_client.get_signing_key_from_jwt(id_token).key
        issuer = f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"
        verify_iss = self.tenant_id not in {"common", "organizations", "consumers"}
        options = {"verify_aud": True, "verify_iss": verify_iss}
        return jwt.decode(
            id_token,
            signing_key,
            algorithms=["RS256"],
            audience=self.client_id,
            issuer=issuer if verify_iss else None,
            options=options,
        )
