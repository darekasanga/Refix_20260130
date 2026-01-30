"""
Apps / HTML distribution management service.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.database import get_connection, init_db


APP_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,48}$")


@dataclass(frozen=True)
class AppAsset:
    id: str
    app_key: str
    app_name: str
    filename: str
    version_label: str
    version_number: int
    storage_path: str
    updated_by_admin_id: str
    updated_at: str
    is_latest: bool


class AppsService:
    def __init__(self, base_dir: Path | None = None) -> None:
        init_db()
        self._base_dir = base_dir or Path(__file__).resolve().parent.parent / "data" / "apps"
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def list_latest(self) -> list[AppAsset]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM app_html_assets
                WHERE is_latest = 1
                ORDER BY datetime(updated_at) DESC
                """
            ).fetchall()
        return [self._hydrate(row) for row in rows]

    def get_latest(self, app_key: str) -> AppAsset | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM app_html_assets
                WHERE app_key = ? AND is_latest = 1
                ORDER BY datetime(updated_at) DESC
                LIMIT 1
                """,
                (app_key,),
            ).fetchone()
        return self._hydrate(row) if row else None

    def save_upload(
        self,
        *,
        app_key: str,
        app_name: str,
        filename: str,
        content: bytes,
        admin_id: str,
        updated_by_label: str,
    ) -> AppAsset:
        if not APP_KEY_RE.match(app_key):
            raise ValueError("Invalid app_key")
        now = datetime.now(timezone.utc).isoformat()
        version_number = self._next_version_number(app_key)
        version_label = f"v{version_number} / {updated_by_label} / {now[:10]}"
        asset_id = str(uuid.uuid4())
        storage_dir = self._base_dir / app_key / asset_id
        storage_dir.mkdir(parents=True, exist_ok=True)
        storage_path = storage_dir / filename
        storage_path.write_bytes(content)
        with get_connection() as conn:
            conn.execute(
                "UPDATE app_html_assets SET is_latest = 0 WHERE app_key = ?",
                (app_key,),
            )
            conn.execute(
                """
                INSERT INTO app_html_assets (
                    id, app_key, app_name, filename, version_label, version_number,
                    storage_path, updated_by_admin_id, updated_at, is_latest
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    asset_id,
                    app_key,
                    app_name,
                    filename,
                    version_label,
                    version_number,
                    str(storage_path),
                    admin_id,
                    now,
                ),
            )
            conn.commit()
        return AppAsset(
            id=asset_id,
            app_key=app_key,
            app_name=app_name,
            filename=filename,
            version_label=version_label,
            version_number=version_number,
            storage_path=str(storage_path),
            updated_by_admin_id=admin_id,
            updated_at=now,
            is_latest=True,
        )

    def _next_version_number(self, app_key: str) -> int:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT MAX(version_number) AS max_version FROM app_html_assets WHERE app_key = ?",
                (app_key,),
            ).fetchone()
        max_version = row["max_version"] if row else None
        return int(max_version or 0) + 1

    def _hydrate(self, row: Any) -> AppAsset:
        return AppAsset(
            id=row["id"],
            app_key=row["app_key"],
            app_name=row["app_name"],
            filename=row["filename"],
            version_label=row["version_label"],
            version_number=row["version_number"],
            storage_path=row["storage_path"],
            updated_by_admin_id=row["updated_by_admin_id"],
            updated_at=row["updated_at"],
            is_latest=bool(row["is_latest"]),
        )
