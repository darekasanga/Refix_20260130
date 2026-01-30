"""
Admin authentication and Wi-Fi local settings management service.
"""

from __future__ import annotations

import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from api.admin_security import decrypt_secret, encrypt_secret, hash_password, verify_password
from api.database import get_connection, init_db


LOCKOUT_MINUTES = 10
MAX_FAILED_ATTEMPTS = 5


@dataclass
class AdminLoginResult:
    admin_id: str
    username: str
    must_change_password: bool


class AdminAuthError(Exception):
    """Base class for admin auth errors."""


class AdminLocked(AdminAuthError):
    """Raised when account is locked."""


class AdminInvalidCredentials(AdminAuthError):
    """Raised on invalid login."""


class AdminAuthService:
    def __init__(self) -> None:
        init_db()
        self._ensure_seed_admin()

    def _ensure_seed_admin(self) -> None:
        with get_connection() as conn:
            existing = conn.execute("SELECT COUNT(*) FROM admin_users").fetchone()[0]
            admin_row = conn.execute(
                "SELECT id FROM admin_users WHERE username = ?",
                ("admin",),
            ).fetchone()
            legacy_row = conn.execute(
                "SELECT id FROM admin_users WHERE username = ?",
                ("admin001",),
            ).fetchone()
            if admin_row:
                return
            password_hash = hash_password("admin01")
            if legacy_row:
                conn.execute(
                    """
                    UPDATE admin_users
                    SET username = ?, password_hash = ?, must_change_password = 1, is_active = 1,
                        failed_attempts = 0, lock_until = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    ("admin", password_hash, legacy_row["id"]),
                )
                conn.commit()
                return
            if existing:
                return
            admin_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO admin_users (
                    id, username, password_hash, must_change_password, is_active
                ) VALUES (?, ?, ?, 1, 1)
                """,
                (admin_id, "admin", password_hash),
            )
            conn.commit()

    def authenticate(self, username: str, password: str) -> AdminLoginResult:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM admin_users WHERE username = ?", (username,)
            ).fetchone()
            if row is None:
                raise AdminInvalidCredentials("Invalid username or password")
            if not row["is_active"]:
                raise AdminInvalidCredentials("Account inactive")
            lock_until = self._parse_ts(row["lock_until"])
            if not verify_password(password, row["password_hash"]):
                if lock_until and lock_until > datetime.now(timezone.utc):
                    raise AdminLocked("Account locked")
                failed = row["failed_attempts"] + 1
                lock_until_value = None
                if failed >= MAX_FAILED_ATTEMPTS:
                    lock_until_value = datetime.now(timezone.utc) + timedelta(
                        minutes=LOCKOUT_MINUTES
                    )
                    failed = 0
                conn.execute(
                    """
                    UPDATE admin_users
                    SET failed_attempts = ?, lock_until = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (failed, self._format_ts(lock_until_value), row["id"]),
                )
                conn.commit()
                raise AdminInvalidCredentials("Invalid username or password")
            if lock_until and lock_until > datetime.now(timezone.utc):
                conn.execute(
                    """
                    UPDATE admin_users
                    SET failed_attempts = 0, lock_until = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (row["id"],),
                )
                conn.commit()
            conn.execute(
                """
                UPDATE admin_users
                SET failed_attempts = 0, lock_until = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (row["id"],),
            )
            conn.commit()
            return AdminLoginResult(
                admin_id=row["id"],
                username=row["username"],
                must_change_password=bool(row["must_change_password"]),
            )

    def change_password(self, admin_id: str, new_password: str) -> None:
        password_hash = hash_password(new_password)
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE admin_users
                SET password_hash = ?, must_change_password = 0, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (password_hash, admin_id),
            )
            conn.commit()

    def get_admin(self, admin_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM admin_users WHERE id = ?", (admin_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def _parse_ts(raw: Any) -> datetime | None:
        if not raw:
            return None
        if isinstance(raw, datetime):
            return raw.replace(tzinfo=timezone.utc)
        try:
            return datetime.fromisoformat(str(raw)).replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    @staticmethod
    def _format_ts(value: datetime | None) -> str | None:
        return value.isoformat() if value else None


class WifiLocalSettingsService:
    def __init__(self) -> None:
        init_db()

    def get_settings(self, site_id: str | None = None) -> dict[str, Any]:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM wifi_local_settings
                WHERE (? IS NULL AND site_id IS NULL) OR site_id = ?
                """,
                (site_id, site_id),
            ).fetchone()
            if row:
                return self._hydrate(row)
        return self._default_settings()

    def update_settings(self, admin_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        site_id = payload.get("site_id")
        record = {
            "id": payload.get("id") or str(uuid.uuid4()),
            "site_id": site_id,
            "enabled": 1 if payload.get("enabled") else 0,
            "ssid": payload.get("ssid"),
            "local_api_base_url": payload["local_api_base_url"],
            "local_api_port": payload.get("local_api_port"),
            "allowed_cidr_list": json.dumps(payload.get("allowed_cidr_list") or []),
            "device_shared_secret_enc": encrypt_secret(payload["device_shared_secret"]),
            "heartbeat_interval_sec": payload.get("heartbeat_interval_sec", 15),
            "updated_by_admin_id": admin_id,
        }
        with get_connection() as conn:
            existing = conn.execute(
                """
                SELECT id FROM wifi_local_settings
                WHERE (? IS NULL AND site_id IS NULL) OR site_id = ?
                """,
                (site_id, site_id),
            ).fetchone()
            if existing:
                record["id"] = existing["id"]
                conn.execute(
                    """
                    UPDATE wifi_local_settings
                    SET enabled = ?, ssid = ?, local_api_base_url = ?, local_api_port = ?,
                        allowed_cidr_list = ?, device_shared_secret_enc = ?,
                        heartbeat_interval_sec = ?, updated_by_admin_id = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        record["enabled"],
                        record["ssid"],
                        record["local_api_base_url"],
                        record["local_api_port"],
                        record["allowed_cidr_list"],
                        record["device_shared_secret_enc"],
                        record["heartbeat_interval_sec"],
                        record["updated_by_admin_id"],
                        record["id"],
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO wifi_local_settings (
                        id, site_id, enabled, ssid, local_api_base_url, local_api_port,
                        allowed_cidr_list, device_shared_secret_enc, heartbeat_interval_sec,
                        updated_by_admin_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"],
                        record["site_id"],
                        record["enabled"],
                        record["ssid"],
                        record["local_api_base_url"],
                        record["local_api_port"],
                        record["allowed_cidr_list"],
                        record["device_shared_secret_enc"],
                        record["heartbeat_interval_sec"],
                        record["updated_by_admin_id"],
                    ),
                )
            conn.commit()
        return self.get_settings(site_id)

    def regenerate_shared_secret(self) -> str:
        return secrets.token_urlsafe(24)

    def log_audit(self, admin_id: str, action: str, meta: dict[str, Any] | None = None) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO admin_audit_logs (id, actor_admin_id, action, meta_json)
                VALUES (?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), admin_id, action, json.dumps(meta or {})),
            )
            conn.commit()

    def _hydrate(self, row: Any) -> dict[str, Any]:
        return {
            "id": row["id"],
            "site_id": row["site_id"],
            "enabled": bool(row["enabled"]),
            "ssid": row["ssid"],
            "local_api_base_url": row["local_api_base_url"],
            "local_api_port": row["local_api_port"],
            "allowed_cidr_list": json.loads(row["allowed_cidr_list"] or "[]"),
            "device_shared_secret": decrypt_secret(row["device_shared_secret_enc"]),
            "heartbeat_interval_sec": row["heartbeat_interval_sec"],
            "updated_by_admin_id": row["updated_by_admin_id"],
            "updated_at": row["updated_at"],
        }

    def _default_settings(self) -> dict[str, Any]:
        return {
            "id": None,
            "site_id": None,
            "enabled": False,
            "ssid": None,
            "local_api_base_url": "http://192.168.10.2:8787",
            "local_api_port": None,
            "allowed_cidr_list": [],
            "device_shared_secret": self.regenerate_shared_secret(),
            "heartbeat_interval_sec": 15,
            "updated_by_admin_id": None,
            "updated_at": None,
        }
