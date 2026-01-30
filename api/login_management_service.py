"""
Login management settings storage service.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from api.database import get_connection, init_db


class LoginManagementService:
    def __init__(self) -> None:
        init_db()

    def get_entries(self) -> list[dict[str, Any]]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT payload_json FROM login_management_settings ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        if not row:
            return []
        try:
            payload = json.loads(row["payload_json"] or "[]")
        except json.JSONDecodeError:
            return []
        return payload if isinstance(payload, list) else []

    def update_entries(self, admin_id: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        record_id = str(uuid.uuid4())
        payload_json = json.dumps(entries, ensure_ascii=False)
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM login_management_settings ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
            if existing:
                record_id = existing["id"]
                conn.execute(
                    """
                    UPDATE login_management_settings
                    SET payload_json = ?, updated_by_admin_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (payload_json, admin_id, record_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO login_management_settings (id, payload_json, updated_by_admin_id)
                    VALUES (?, ?, ?)
                    """,
                    (record_id, payload_json, admin_id),
                )
            conn.commit()
        return self.get_entries()
