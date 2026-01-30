"""
FastAPI local operation settings service.
"""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from api.admin_security import decrypt_secret, encrypt_secret
from api.database import get_connection, init_db


class FastApiSettingsService:
    def __init__(self) -> None:
        init_db()

    def get_settings(self) -> dict[str, Any]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM fastapi_settings ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        if row:
            return self._hydrate(row)
        return self._default_settings()

    def update_settings(self, admin_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = {
            "id": payload.get("id") or str(uuid.uuid4()),
            "enabled": 1 if payload.get("enabled") else 0,
            "allowed_cidr_list": json.dumps(payload.get("allowed_cidr_list") or []),
            "shared_token_enc": encrypt_secret(payload["shared_token"]),
            "local_mode": 1 if payload.get("local_mode") else 0,
            "require_save_token": 1 if payload.get("require_save_token") else 0,
            "require_sync_token": 1 if payload.get("require_sync_token") else 0,
            "require_latest_token": 1 if payload.get("require_latest_token") else 0,
            "updated_by_admin_id": admin_id,
        }
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM fastapi_settings ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
            if existing:
                record["id"] = existing["id"]
                conn.execute(
                    """
                    UPDATE fastapi_settings
                    SET enabled = ?, allowed_cidr_list = ?, shared_token_enc = ?,
                        local_mode = ?, require_save_token = ?, require_sync_token = ?,
                        require_latest_token = ?, updated_by_admin_id = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        record["enabled"],
                        record["allowed_cidr_list"],
                        record["shared_token_enc"],
                        record["local_mode"],
                        record["require_save_token"],
                        record["require_sync_token"],
                        record["require_latest_token"],
                        record["updated_by_admin_id"],
                        record["id"],
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO fastapi_settings (
                        id, enabled, allowed_cidr_list, shared_token_enc,
                        local_mode, require_save_token, require_sync_token,
                        require_latest_token, updated_by_admin_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"],
                        record["enabled"],
                        record["allowed_cidr_list"],
                        record["shared_token_enc"],
                        record["local_mode"],
                        record["require_save_token"],
                        record["require_sync_token"],
                        record["require_latest_token"],
                        record["updated_by_admin_id"],
                    ),
                )
            conn.commit()
        return self.get_settings()

    def regenerate_token(self) -> str:
        return secrets.token_urlsafe(32)

    def _hydrate(self, row: Any) -> dict[str, Any]:
        return {
            "id": row["id"],
            "enabled": bool(row["enabled"]),
            "allowed_cidr_list": json.loads(row["allowed_cidr_list"] or "[]"),
            "shared_token": decrypt_secret(row["shared_token_enc"]),
            "local_mode": bool(row["local_mode"]),
            "require_save_token": bool(row["require_save_token"]),
            "require_sync_token": bool(row["require_sync_token"]),
            "require_latest_token": bool(row["require_latest_token"]),
            "updated_by_admin_id": row["updated_by_admin_id"],
            "updated_at": row["updated_at"],
        }

    def _default_settings(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "id": None,
            "enabled": True,
            "allowed_cidr_list": [],
            "shared_token": self.regenerate_token(),
            "local_mode": True,
            "require_save_token": True,
            "require_sync_token": True,
            "require_latest_token": False,
            "updated_by_admin_id": None,
            "updated_at": now,
        }
