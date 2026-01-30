"""
Local Wi-Fi data storage service for latest/history datasets.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from api.database import get_connection, init_db


@dataclass(frozen=True)
class LocalDatasetRecord:
    id: str
    version_label: str
    updated_at: str
    updated_by: str
    payload: Any


class LocalDatasetService:
    def __init__(self) -> None:
        init_db()

    def get_latest(self) -> LocalDatasetRecord | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, version_label, updated_at, updated_by, payload_json
                FROM wifi_local_datasets
                ORDER BY datetime(updated_at) DESC, created_at DESC
                LIMIT 1
                """
            ).fetchone()
        return self._hydrate(row) if row else None

    def list_history(self, limit: int | None = None) -> list[LocalDatasetRecord]:
        query = (
            "SELECT id, version_label, updated_at, updated_by, payload_json "
            "FROM wifi_local_datasets ORDER BY datetime(updated_at) DESC, created_at DESC"
        )
        params: tuple[Any, ...] = ()
        if limit:
            query += " LIMIT ?"
            params = (limit,)
        with get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._hydrate(row) for row in rows]

    def save_dataset(
        self,
        *,
        payload: Any,
        version_label: str,
        updated_by: str,
        updated_at: str | None = None,
    ) -> LocalDatasetRecord:
        now = datetime.now(timezone.utc).isoformat()
        record_id = str(uuid.uuid4())
        record_updated_at = updated_at or now
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO wifi_local_datasets (
                    id, version_label, updated_at, updated_by, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    version_label,
                    record_updated_at,
                    updated_by,
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            conn.commit()
        return LocalDatasetRecord(
            id=record_id,
            version_label=version_label,
            updated_at=record_updated_at,
            updated_by=updated_by,
            payload=payload,
        )

    @staticmethod
    def _hydrate(row: Any) -> LocalDatasetRecord:
        return LocalDatasetRecord(
            id=row["id"],
            version_label=row["version_label"],
            updated_at=row["updated_at"],
            updated_by=row["updated_by"],
            payload=json.loads(row["payload_json"] or "null"),
        )
