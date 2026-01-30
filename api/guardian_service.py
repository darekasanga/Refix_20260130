"""
Database access layer for guardian notifications and linking.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets
import uuid
from typing import Iterable

from api.database import get_connection, init_db


class GuardianService:
    def __init__(self) -> None:
        init_db()

    @staticmethod
    def _hash_value(value: str, pepper: str) -> str:
        return hashlib.sha256(f"{value}{pepper}".encode("utf-8")).hexdigest()

    @staticmethod
    def _mask_phone(phone_e164: str) -> str:
        digits = "".join(ch for ch in phone_e164 if ch.isdigit())
        if len(digits) <= 4:
            return phone_e164
        masked = f"{digits[:-4]}{'*' * 4}{digits[-4:]}"
        if phone_e164.startswith("+"):
            return f"+{masked}"
        return masked

    def get_user_by_identity(self, provider: str, external_id: str) -> dict | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT u.*
                FROM users u
                INNER JOIN user_identities ui ON ui.user_id = u.id
                WHERE ui.provider = ? AND ui.external_id = ?
                """,
                (provider, external_id),
            ).fetchone()
        return dict(row) if row else None

    def upsert_identity(
        self, provider: str, external_id: str, display_hint: str | None = None
    ) -> dict:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT u.*
                FROM users u
                INNER JOIN user_identities ui ON ui.user_id = u.id
                WHERE ui.provider = ? AND ui.external_id = ?
                """,
                (provider, external_id),
            ).fetchone()
            if row:
                return dict(row)

            user_id = str(uuid.uuid4())
            identity_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO users (id)
                VALUES (?)
                """,
                (user_id,),
            )
            conn.execute(
                """
                INSERT INTO user_identities (id, user_id, provider, external_id, display_hint)
                VALUES (?, ?, ?, ?, ?)
                """,
                (identity_id, user_id, provider, external_id, display_hint),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row)

    def create_sms_challenge(
        self,
        *,
        phone_e164: str,
        code: str,
        purpose: str,
        ttl_seconds: int,
        tries_left: int,
        pepper: str,
    ) -> dict:
        challenge_id = str(uuid.uuid4())
        expires_at = dt.datetime.utcnow() + dt.timedelta(seconds=ttl_seconds)
        phone_hash = self._hash_value(phone_e164, pepper)
        code_hash = self._hash_value(code, pepper)
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sms_challenges (
                    id, phone_e164, phone_hash, code_hash, purpose,
                    expires_at, tries_left
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    challenge_id,
                    self._mask_phone(phone_e164),
                    phone_hash,
                    code_hash,
                    purpose,
                    expires_at.isoformat(sep=" ", timespec="seconds"),
                    tries_left,
                ),
            )
            row = conn.execute(
                "SELECT * FROM sms_challenges WHERE id = ?",
                (challenge_id,),
            ).fetchone()
        return dict(row)

    def verify_sms_challenge(
        self,
        *,
        challenge_id: str,
        code: str,
        pepper: str,
    ) -> dict | None:
        now = dt.datetime.utcnow()
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sms_challenges WHERE id = ?",
                (challenge_id,),
            ).fetchone()
            if not row:
                return None
            if row["consumed_at"]:
                return None
            if dt.datetime.fromisoformat(row["expires_at"]) < now:
                return None
            if row["tries_left"] <= 0:
                return None
            expected = row["code_hash"]
            supplied = self._hash_value(code, pepper)
            if not secrets.compare_digest(expected, supplied):
                conn.execute(
                    """
                    UPDATE sms_challenges
                    SET tries_left = tries_left - 1
                    WHERE id = ?
                    """,
                    (challenge_id,),
                )
                return None
            conn.execute(
                """
                UPDATE sms_challenges
                SET consumed_at = ?
                WHERE id = ?
                """,
                (now.isoformat(sep=" ", timespec="seconds"), challenge_id),
            )
        return dict(row)

    def count_recent_sms_challenges(self, phone_hash: str, *, seconds: int) -> int:
        since = dt.datetime.utcnow() - dt.timedelta(seconds=seconds)
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM sms_challenges
                WHERE phone_hash = ? AND created_at >= ?
                """,
                (phone_hash, since.isoformat(sep=" ", timespec="seconds")),
            ).fetchone()
        return int(row["count"]) if row else 0

    def find_child_id_by_statement(self, statement_id: str) -> str | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT child_id FROM daily_nodes WHERE statement_id = ?",
                (statement_id,),
            ).fetchone()
        return row["child_id"] if row else None

    def upsert_link(self, user_id: str, child_id: str, linked_via: str) -> dict:
        valid_from = dt.date.today().isoformat()
        link_id = str(uuid.uuid4())
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO guardian_links (
                    id, user_id, child_id, linked_via, valid_from,
                    is_active
                )
                VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(user_id, child_id) DO UPDATE SET
                    is_active = 1,
                    linked_via = excluded.linked_via,
                    valid_from = excluded.valid_from,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (link_id, user_id, child_id, linked_via, valid_from),
            )
            row = conn.execute(
                """
                SELECT * FROM guardian_links
                WHERE user_id = ? AND child_id = ?
                """,
                (user_id, child_id),
            ).fetchone()
        return dict(row)

    def get_link(self, user_id: str, child_id: str) -> dict | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM guardian_links
                WHERE user_id = ? AND child_id = ? AND is_active = 1
                """,
                (user_id, child_id),
            ).fetchone()
        return dict(row) if row else None

    def get_links(self, user_id: str) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT child_id, valid_from, is_active, created_at
                FROM guardian_links
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def count_links(self, user_id: str) -> int:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM guardian_links
                WHERE user_id = ? AND is_active = 1
                """,
                (user_id,),
            ).fetchone()
        return int(row["count"]) if row else 0

    def count_links_for_child(self, child_id: str) -> int:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM guardian_links
                WHERE child_id = ? AND is_active = 1
                """,
                (child_id,),
            ).fetchone()
        return int(row["count"]) if row else 0

    def get_children(self, user_id: str) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT gl.child_id, c.display_label, c.external_child_id
                FROM guardian_links gl
                LEFT JOIN children c ON c.id = gl.child_id
                WHERE gl.user_id = ? AND gl.is_active = 1
                ORDER BY gl.created_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_thread_by_child(self, child_id: str) -> dict | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM notification_threads
                WHERE child_id = ? AND status = 'OPEN'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (child_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_thread(self, thread_id: str) -> dict | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM notification_threads WHERE id = ?",
                (thread_id,),
            ).fetchone()
        return dict(row) if row else None

    def upsert_thread(self, child_id: str, staff_id: str | None) -> dict:
        existing = self.get_thread_by_child(child_id)
        if existing:
            return existing
        thread_id = str(uuid.uuid4())
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO notification_threads (
                    id, child_id, status, created_by_staff_id
                )
                VALUES (?, ?, 'OPEN', ?)
                """,
                (thread_id, child_id, staff_id),
            )
            row = conn.execute(
                "SELECT * FROM notification_threads WHERE id = ?",
                (thread_id,),
            ).fetchone()
        return dict(row)

    def list_messages(self, thread_id: str) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM notification_messages
                WHERE thread_id = ?
                ORDER BY created_at ASC
                """,
                (thread_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_message(
        self,
        *,
        thread_id: str,
        sender_type: str,
        sender_id: str,
        body_text: str,
    ) -> dict:
        message_id = str(uuid.uuid4())
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO notification_messages (
                    id, thread_id, sender_type, sender_id, body_text
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (message_id, thread_id, sender_type, sender_id, body_text),
            )
            row = conn.execute(
                "SELECT * FROM notification_messages WHERE id = ?",
                (message_id,),
            ).fetchone()
        return dict(row)

    def mark_read(self, *, thread_id: str, reader_type: str, reader_id: str) -> None:
        read_id = str(uuid.uuid4())
        now = dt.datetime.utcnow().isoformat(sep=" ", timespec="seconds")
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO notification_reads (id, thread_id, reader_type, reader_id, last_read_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(thread_id, reader_type, reader_id) DO UPDATE SET
                    last_read_at = excluded.last_read_at
                """,
                (read_id, thread_id, reader_type, reader_id, now),
            )

    def get_last_read_at(
        self, *, thread_id: str, reader_type: str, reader_id: str
    ) -> dt.datetime | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT last_read_at
                FROM notification_reads
                WHERE thread_id = ? AND reader_type = ? AND reader_id = ?
                """,
                (thread_id, reader_type, reader_id),
            ).fetchone()
        if not row:
            return None
        return dt.datetime.fromisoformat(row["last_read_at"])

    def get_unread_count(
        self,
        *,
        thread_id: str,
        reader_type: str,
        reader_id: str,
        sender_types: Iterable[str],
    ) -> int:
        last_read = self.get_last_read_at(
            thread_id=thread_id, reader_type=reader_type, reader_id=reader_id
        )
        sender_placeholders = ",".join("?" for _ in sender_types)
        params: list = [thread_id, *sender_types]
        query = f"""
            SELECT COUNT(*) AS count
            FROM notification_messages
            WHERE thread_id = ?
              AND sender_type IN ({sender_placeholders})
        """
        if last_read:
            query += " AND created_at > ?"
            params.append(last_read.isoformat())
        with get_connection() as conn:
            row = conn.execute(query, params).fetchone()
        return int(row["count"]) if row else 0

    def get_last_message_at(self, thread_id: str) -> str | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT created_at
                FROM notification_messages
                WHERE thread_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (thread_id,),
            ).fetchone()
        return row["created_at"] if row else None

    def create_qr_token_record(
        self,
        *,
        thread_id: str,
        child_id: str,
        ttl_seconds: int,
    ) -> dict:
        token_id = str(uuid.uuid4())
        now = dt.datetime.utcnow()
        expires_at = now + dt.timedelta(seconds=ttl_seconds)
        nonce = secrets.token_urlsafe(12)
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO notify_qr_tokens (id, thread_id, child_id, expires_at, nonce)
                VALUES (?, ?, ?, ?, ?)
                """,
                (token_id, thread_id, child_id, expires_at.isoformat(sep=" ", timespec="seconds"), nonce),
            )
            row = conn.execute(
                "SELECT * FROM notify_qr_tokens WHERE id = ?",
                (token_id,),
            ).fetchone()
        return dict(row)

    def consume_qr_token(self, token_id: str) -> dict | None:
        now = dt.datetime.utcnow()
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM notify_qr_tokens WHERE id = ?",
                (token_id,),
            ).fetchone()
            if not row:
                return None
            if row["consumed_at"]:
                return None
            if dt.datetime.fromisoformat(row["expires_at"]) < now:
                return None
            conn.execute(
                """
                UPDATE notify_qr_tokens
                SET consumed_at = ?
                WHERE id = ?
                """,
                (now.isoformat(sep=" ", timespec="seconds"), token_id),
            )
        return dict(row)
