"""
Daily node versioning and rebuild logic.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from api.database import get_connection, init_db

POLICY_VERSION = "v1"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_payload(raw: str | None) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
    if isinstance(payload, dict):
        return payload
    return {"value": payload}


def _serialize_inputs(inputs: Dict[str, Any]) -> str:
    return json.dumps(inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_inputs(inputs: Dict[str, Any]) -> str:
    serialized = _serialize_inputs(inputs).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _sum_numeric(values: List[Any]) -> int:
    total = 0
    for value in values:
        if isinstance(value, (int, float)):
            total += int(value)
    return total


@dataclass(frozen=True)
class DailyNodeRebuildResult:
    action: str
    node: Dict[str, Any] | None


class DailyNodeService:
    def __init__(self) -> None:
        init_db()

    def get_active(self, *, child_id: str, date: str) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM daily_nodes
                WHERE child_id = ? AND date = ? AND status = 'ACTIVE'
                """,
                (child_id, date),
            ).fetchone()
        return dict(row) if row else None

    def get_history(self, *, child_id: str, date: str) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM daily_nodes
                WHERE child_id = ? AND date = ?
                ORDER BY version DESC
                """,
                (child_id, date),
            ).fetchall()
        return [dict(row) for row in rows]

    def rebuild(
        self,
        *,
        child_id: str,
        date: str,
        change_reason_code: str,
        change_note: str | None = None,
    ) -> DailyNodeRebuildResult:
        inputs = self._collect_inputs(child_id=child_id, date=date)
        inputs_hash = _hash_inputs(inputs)
        with get_connection() as conn:
            existing = conn.execute(
                """
                SELECT * FROM daily_nodes
                WHERE child_id = ? AND date = ? AND status = 'ACTIVE'
                """,
                (child_id, date),
            ).fetchone()
            if existing and existing["inputs_hash"] == inputs_hash:
                return DailyNodeRebuildResult(action="noop", node=dict(existing))

            if existing:
                new_version = existing["version"] + 1
                statement_id = existing["statement_id"]
            else:
                new_version = 1
                statement_id = uuid.uuid4().hex

            supersedes_id = existing["id"] if existing else None
            new_node = self._build_node_payload(
                child_id=child_id,
                date=date,
                version=new_version,
                inputs_hash=inputs_hash,
                statement_id=statement_id,
                change_reason_code=change_reason_code,
                change_note=change_note,
                inputs=inputs,
                supersedes_id=supersedes_id,
            )
            new_node_id = new_node["id"]
            now = new_node["valid_from"]

            if existing:
                conn.execute(
                    """
                    UPDATE daily_nodes
                    SET status = 'SUPERSEDED',
                        valid_to = ?,
                        superseded_by_id = ?
                    WHERE id = ?
                    """,
                    (now, new_node_id, existing["id"]),
                )

            conn.execute(
                """
                INSERT INTO daily_nodes (
                    id, child_id, date, version, status, valid_from, valid_to,
                    supersedes_id, superseded_by_id, change_reason_code, change_note,
                    statement_id, inputs_hash, derived_category_code, raw_minutes,
                    ext_minutes, state_token, dict_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_node["id"],
                    new_node["child_id"],
                    new_node["date"],
                    new_node["version"],
                    new_node["status"],
                    new_node["valid_from"],
                    new_node["valid_to"],
                    new_node["supersedes_id"],
                    new_node["superseded_by_id"],
                    new_node["change_reason_code"],
                    new_node["change_note"],
                    new_node["statement_id"],
                    new_node["inputs_hash"],
                    new_node["derived_category_code"],
                    new_node["raw_minutes"],
                    new_node["ext_minutes"],
                    new_node["state_token"],
                    new_node["dict_id"],
                ),
            )
            self._append_calc_history(
                conn,
                daily_node_id=new_node_id,
                payload={
                    "inputs_hash": inputs_hash,
                    "derived_category_code": new_node["derived_category_code"],
                    "raw_minutes": new_node["raw_minutes"],
                    "ext_minutes": new_node["ext_minutes"],
                    "policy_version": POLICY_VERSION,
                },
            )
            conn.commit()

        action = "superseded" if existing else "created"
        return DailyNodeRebuildResult(action=action, node=new_node)

    def _collect_inputs(self, *, child_id: str, date: str) -> Dict[str, Any]:
        month = date[:7]
        with get_connection() as conn:
            raw_events = conn.execute(
                """
                SELECT id, event_type, payload, created_at
                FROM raw_attendance_events
                WHERE child_id = ? AND date = ?
                ORDER BY id ASC
                """,
                (child_id, date),
            ).fetchall()
            base = conn.execute(
                """
                SELECT base_category_code
                FROM child_month_profiles
                WHERE child_id = ? AND month = ?
                """,
                (child_id, month),
            ).fetchone()
            node_events = conn.execute(
                """
                SELECT id, event_type, payload, created_at
                FROM daily_node_events
                WHERE child_id = ? AND date = ?
                ORDER BY id ASC
                """,
                (child_id, date),
            ).fetchall()

        return {
            "raw_attendance_events": [
                {k: v for k, v in dict(row).items() if k not in ("id", "created_at")}
                for row in raw_events
            ],
            "base_category_code": base["base_category_code"] if base else None,
            "daily_node_events": [
                {k: v for k, v in dict(row).items() if k not in ("id", "created_at")}
                for row in node_events
            ],
            "policy_version": POLICY_VERSION,
        }

    def _build_node_payload(
        self,
        *,
        child_id: str,
        date: str,
        version: int,
        inputs_hash: str,
        statement_id: str,
        change_reason_code: str,
        change_note: str | None,
        inputs: Dict[str, Any],
        supersedes_id: str | None,
    ) -> Dict[str, Any]:
        now = _utcnow()
        derived_category_code = inputs.get("base_category_code")
        ext_minutes = 0
        raw_minutes = 0

        raw_payloads = [_parse_payload(event.get("payload")) for event in inputs["raw_attendance_events"]]
        raw_minutes = _sum_numeric([payload.get("minutes") for payload in raw_payloads])

        node_payloads = [_parse_payload(event.get("payload")) for event in inputs["daily_node_events"]]
        for payload in node_payloads:
            if payload.get("derived_category_code"):
                derived_category_code = payload.get("derived_category_code")
            ext_value = payload.get("ext_minutes")
            if isinstance(ext_value, (int, float, str)):
                try:
                    ext_minutes += int(ext_value)
                except (ValueError, TypeError):
                    # Ignore non-numeric ext_minutes values
                    pass

        return {
            "id": uuid.uuid4().hex,
            "child_id": child_id,
            "date": date,
            "version": version,
            "status": "ACTIVE",
            "valid_from": now,
            "valid_to": None,
            "supersedes_id": supersedes_id,
            "superseded_by_id": None,
            "change_reason_code": change_reason_code,
            "change_note": change_note,
            "statement_id": statement_id,
            "inputs_hash": inputs_hash,
            "derived_category_code": derived_category_code,
            "raw_minutes": raw_minutes,
            "ext_minutes": ext_minutes,
            "state_token": secrets.token_urlsafe(32),
            "dict_id": secrets.token_urlsafe(16),
        }

    def _append_calc_history(
        self, conn, *, daily_node_id: str, payload: Dict[str, Any]
    ) -> None:
        conn.execute(
            """
            INSERT INTO calc_history (daily_node_id, payload)
            VALUES (?, ?)
            """,
            (daily_node_id, _serialize_inputs(payload)),
        )
