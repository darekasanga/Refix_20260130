"""
LINE Messaging API helpers for webhook handling and push delivery.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from api.database import get_connection, init_db


LINE_REPLY_ENDPOINT = "https://api.line.me/v2/bot/message/reply"
LINE_PUSH_ENDPOINT = "https://api.line.me/v2/bot/message/push"


class LineMessagingError(Exception):
    """Base error for LINE messaging helpers."""


class LineMessagingConfigError(LineMessagingError):
    """Raised when LINE configuration is missing."""


class LineMessagingRequestError(LineMessagingError):
    """Raised when LINE API returns an error response."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise LineMessagingConfigError(f"{name} is required.")
    return value


def verify_signature(body: bytes, signature: str, channel_secret: str) -> bool:
    if not signature:
        return False
    mac = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def _line_headers(channel_access_token: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {channel_access_token}",
    }


def _post_line(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    channel_access_token = _require_env("LINE_CHANNEL_ACCESS_TOKEN")
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, headers=_line_headers(channel_access_token), method="POST")
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)
    except (HTTPError, URLError) as err:
        status = getattr(err, "code", None)
        raise LineMessagingRequestError(f"LINE API request failed: {status}")


def reply_message(reply_token: str, messages: list[dict[str, Any]]) -> None:
    if not reply_token:
        return
    _post_line(LINE_REPLY_ENDPOINT, {"replyToken": reply_token, "messages": messages})


def push_message(line_user_id: str, messages: list[dict[str, Any]]) -> None:
    _post_line(LINE_PUSH_ENDPOINT, {"to": line_user_id, "messages": messages})


@dataclass(frozen=True)
class StatementPayload:
    statement_id: str
    nursery_name: str
    target_month: str
    total_amount: str


@dataclass(frozen=True)
class EventPayload:
    event_id: str
    title: str
    date: str


def build_statement_flex(payload: StatementPayload) -> dict[str, Any]:
    return {
        "type": "flex",
        "altText": "明細のお知らせ",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": payload.nursery_name, "weight": "bold", "size": "lg"},
                    {"type": "text", "text": f"対象月: {payload.target_month}"},
                    {"type": "text", "text": f"合計金額: {payload.total_amount}", "weight": "bold"},
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "action": {
                            "type": "postback",
                            "label": "確認しました",
                            "data": f"approve:{payload.statement_id}",
                        },
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "action": {
                            "type": "postback",
                            "label": "質問・修正あり",
                            "data": f"comment_request:{payload.statement_id}",
                        },
                    },
                ],
            },
        },
    }


def build_event_flex(payload: EventPayload) -> dict[str, Any]:
    return {
        "type": "flex",
        "altText": "イベント出欠の確認",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": payload.title, "weight": "bold", "size": "lg"},
                    {"type": "text", "text": payload.date},
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "action": {
                            "type": "postback",
                            "label": "参加",
                            "data": f"event_attend:{payload.event_id}",
                        },
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "action": {
                            "type": "postback",
                            "label": "不参加",
                            "data": f"event_absent:{payload.event_id}",
                        },
                    },
                ],
            },
        },
    }


def init_line_db() -> None:
    init_db()


def register_unlinked_user(line_user_id: str) -> None:
    if not line_user_id:
        return
    init_line_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO line_users (line_user_id, status, followed_at)
            VALUES (?, ?, ?)
            ON CONFLICT(line_user_id)
            DO UPDATE SET status = excluded.status
            """,
            (line_user_id, "unlinked", _isoformat(_utcnow())),
        )
        conn.commit()


def get_child_for_line_user(line_user_id: str) -> str | None:
    if not line_user_id:
        return None
    init_line_db()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT child_key
            FROM child_links
            WHERE line_user_id = ?
            ORDER BY linked_at DESC
            LIMIT 1
            """,
            (line_user_id,),
        ).fetchone()
    return row["child_key"] if row else None


def get_line_users_for_child(child_key: str) -> list[str]:
    if not child_key:
        return []
    init_line_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT line_user_id
            FROM child_links
            WHERE child_key = ?
            ORDER BY linked_at DESC
            """,
            (child_key,),
        ).fetchall()
    return [row["line_user_id"] for row in rows]


def record_statement_delivery(
    statement_id: str,
    child_key: str,
    line_user_id: str,
    status: str,
) -> None:
    init_line_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO line_statement_messages (statement_id, child_key, line_user_id, status, sent_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (statement_id, child_key, line_user_id, status, _isoformat(_utcnow())),
        )
        conn.commit()


def record_message_delivery(
    message_type: str,
    child_key: str | None,
    line_user_id: str,
    status: str,
    payload: dict[str, Any],
    statement_id: str | None = None,
    event_id: str | None = None,
) -> None:
    init_line_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO line_message_deliveries (
                message_type, child_key, line_user_id, status, payload, statement_id, event_id, sent_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_type,
                child_key,
                line_user_id,
                status,
                json.dumps(payload, ensure_ascii=False),
                statement_id,
                event_id,
                _isoformat(_utcnow()),
            ),
        )
        conn.commit()


def mark_comment_request(line_user_id: str, statement_id: str) -> None:
    init_line_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO line_comment_requests (line_user_id, statement_id, requested_at)
            VALUES (?, ?, ?)
            ON CONFLICT(line_user_id)
            DO UPDATE SET statement_id = excluded.statement_id, requested_at = excluded.requested_at
            """,
            (line_user_id, statement_id, _isoformat(_utcnow())),
        )
        conn.commit()


def consume_comment_request(line_user_id: str) -> str | None:
    init_line_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT statement_id FROM line_comment_requests WHERE line_user_id = ?",
            (line_user_id,),
        ).fetchone()
        if row:
            conn.execute(
                "DELETE FROM line_comment_requests WHERE line_user_id = ?",
                (line_user_id,),
            )
            conn.commit()
            return row["statement_id"]
    return None


def get_latest_statement_for_user(line_user_id: str) -> str | None:
    init_line_db()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT statement_id
            FROM line_statement_messages
            WHERE line_user_id = ?
            ORDER BY sent_at DESC
            LIMIT 1
            """,
            (line_user_id,),
        ).fetchone()
    return row["statement_id"] if row else None


def update_statement_reply(
    statement_id: str,
    line_user_id: str,
    status: str,
    comment: str | None = None,
    child_key: str | None = None,
) -> None:
    init_line_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO line_statement_replies (statement_id, child_key, line_user_id, status, comment, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(statement_id, line_user_id)
            DO UPDATE SET
                status = excluded.status,
                comment = excluded.comment,
                child_key = COALESCE(excluded.child_key, line_statement_replies.child_key),
                updated_at = excluded.updated_at
            """,
            (
                statement_id,
                child_key,
                line_user_id,
                status,
                comment,
                _isoformat(_utcnow())),
        )
        conn.commit()


def record_event_response(
    event_id: str,
    line_user_id: str,
    status: str,
    child_key: str | None = None,
) -> None:
    init_line_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO line_event_responses (event_id, child_key, line_user_id, status, responded_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(event_id, line_user_id)
            DO UPDATE SET
                status = excluded.status,
                child_key = COALESCE(excluded.child_key, line_event_responses.child_key),
                responded_at = excluded.responded_at
            """,
            (event_id, child_key, line_user_id, status, _isoformat(_utcnow())),
        )
        conn.commit()


def parse_postback(data: str) -> tuple[str, str] | None:
    if not data or ":" not in data:
        return None
    kind, value = data.split(":", 1)
    return kind, value


def extract_text_message(event: dict[str, Any]) -> str | None:
    if event.get("type") != "message":
        return None
    message = event.get("message") or {}
    if message.get("type") != "text":
        return None
    text = message.get("text")
    return text.strip() if isinstance(text, str) else None


def extract_user_id(event: dict[str, Any]) -> str | None:
    source = event.get("source") or {}
    return source.get("userId")


def extract_reply_token(event: dict[str, Any]) -> str | None:
    return event.get("replyToken")


def ensure_env() -> None:
    _require_env("LINE_CHANNEL_SECRET")
    _require_env("LINE_CHANNEL_ACCESS_TOKEN")
