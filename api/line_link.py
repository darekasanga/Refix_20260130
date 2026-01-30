"""
Service helpers for issuing and confirming LINE linkage tokens.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from api.database import get_connection, init_db
from api.security import fingerprint, hash_code, verify_code

OTP_LENGTH = 6
DEFAULT_EXPIRY_DAYS = 7


class LineLinkError(Exception):
    """Base error for LINE link issuance/confirmation."""


class LineLinkNotFound(LineLinkError):
    """Raised when a token/issue record cannot be found."""


class LineLinkExpired(LineLinkError):
    """Raised when a token is expired."""


class LineLinkUsed(LineLinkError):
    """Raised when a token has already been used."""


class LineLinkRevoked(LineLinkError):
    """Raised when a token has been revoked."""


class LineLinkInvalid(LineLinkError):
    """Raised when provided token/otp are invalid."""


@dataclass(frozen=True)
class IssueRecord:
    id: int
    child_key: str
    token: str
    otp: str
    issued_at: str
    expires_at: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


class LineLinkService:
    """Service for issuing and confirming LINE link tokens."""

    def __init__(self) -> None:
        init_db()

    def issue(self, child_key: str, expires_days: int = DEFAULT_EXPIRY_DAYS) -> IssueRecord:
        if not child_key:
            raise LineLinkInvalid("child_key is required.")
        token = secrets.token_urlsafe(24)
        otp = f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"
        issued_at = _utcnow()
        expires_at = issued_at + timedelta(days=expires_days)
        token_salt, token_hash = hash_code(token)
        otp_salt, otp_hash = hash_code(otp)
        token_fp = fingerprint(token)
        otp_fp = fingerprint(otp)

        with get_connection() as conn:
            conn.execute(
                """
                UPDATE link_issues
                SET revoked_at = ?
                WHERE child_key = ?
                  AND used_at IS NULL
                  AND revoked_at IS NULL
                """,
                (_isoformat(issued_at), child_key),
            )
            cur = conn.execute(
                """
                INSERT INTO link_issues (
                    child_key,
                    token_hash,
                    token_salt,
                    token_fingerprint,
                    otp_hash,
                    otp_salt,
                    otp_fingerprint,
                    expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    child_key,
                    token_hash,
                    token_salt,
                    token_fp,
                    otp_hash,
                    otp_salt,
                    otp_fp,
                    _isoformat(expires_at),
                ),
            )
            conn.commit()
            record_id = cur.lastrowid

        return IssueRecord(
            id=record_id,
            child_key=child_key,
            token=token,
            otp=otp,
            issued_at=_isoformat(issued_at),
            expires_at=_isoformat(expires_at),
        )

    def get_active_issue(self, child_key: str) -> Optional[dict]:
        if not child_key:
            raise LineLinkInvalid("child_key is required.")
        now_iso = _isoformat(_utcnow())
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, child_key, issued_at, expires_at
                FROM link_issues
                WHERE child_key = ?
                  AND used_at IS NULL
                  AND revoked_at IS NULL
                  AND expires_at > ?
                ORDER BY issued_at DESC
                LIMIT 1
                """,
                (child_key, now_iso),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def confirm(self, token: str, otp: str, line_user_id: str) -> dict:
        if not token or not otp or not line_user_id:
            raise LineLinkInvalid("token, otp, and line_user_id are required.")

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM link_issues WHERE token_fingerprint = ?",
                (fingerprint(token),),
            ).fetchone()

        if row is None or not verify_code(token, row["token_salt"], row["token_hash"]):
            raise LineLinkNotFound("Token not found.")
        if row["revoked_at"]:
            raise LineLinkRevoked("Token has been revoked.")
        if row["used_at"]:
            raise LineLinkUsed("Token already used.")
        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at <= _utcnow():
            raise LineLinkExpired("Token expired.")
        if not verify_code(otp, row["otp_salt"], row["otp_hash"]):
            raise LineLinkInvalid("OTP is invalid.")

        linked_at = _isoformat(_utcnow())
        with get_connection() as conn:
            conn.execute(
                "UPDATE link_issues SET used_at = ? WHERE id = ?",
                (linked_at, row["id"]),
            )
            conn.execute(
                """
                INSERT INTO child_links (child_key, line_user_id, linked_at)
                VALUES (?, ?, ?)
                ON CONFLICT(child_key, line_user_id)
                DO UPDATE SET linked_at = excluded.linked_at
                """,
                (row["child_key"], line_user_id, linked_at),
            )
            conn.commit()

        return {
            "child_key": row["child_key"],
            "linked_at": linked_at,
        }

    def get_link_status(self, child_keys: Iterable[str]) -> list[dict]:
        keys = [key for key in child_keys if key]
        if not keys:
            return []
        placeholders = ",".join("?" for _ in keys)
        with get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT child_key, line_user_id, linked_at
                FROM child_links
                WHERE child_key IN ({placeholders})
                ORDER BY linked_at DESC
                """,
                keys,
            ).fetchall()
        latest = {}
        for row in rows:
            if row["child_key"] not in latest:
                latest[row["child_key"]] = row
        items = []
        for key in keys:
            record = latest.get(key)
            linked_at = record["linked_at"] if record else None
            items.append(
                {
                    "child_key": key,
                    "linked": bool(linked_at),
                    "linked_line_user_id": record["line_user_id"] if record else None,
                    "linked_at": linked_at,
                }
            )
        return items
