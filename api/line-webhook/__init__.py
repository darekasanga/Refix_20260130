import json
import os

import azure.functions as func

from api.line_messaging import (
    LineMessagingConfigError,
    extract_reply_token,
    extract_text_message,
    extract_user_id,
    get_child_for_line_user,
    get_latest_statement_for_user,
    mark_comment_request,
    parse_postback,
    register_unlinked_user,
    reply_message,
    update_statement_reply,
    consume_comment_request,
    verify_signature,
    record_event_response,
)


def _json_response(payload: dict, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(payload, ensure_ascii=False),
        mimetype="application/json",
        status_code=status_code,
    )


def _get_channel_secret() -> str:
    secret = os.getenv("LINE_CHANNEL_SECRET")
    if not secret:
        raise LineMessagingConfigError("LINE_CHANNEL_SECRET is required.")
    return secret


def _handle_follow(event: dict) -> None:
    line_user_id = extract_user_id(event)
    if not line_user_id:
        return
    register_unlinked_user(line_user_id)
    reply_token = extract_reply_token(event)
    if reply_token:
        reply_message(
            reply_token,
            [
                {
                    "type": "text",
                    "text": "登録ありがとうございます。園で案内された手順で連携を完了してください。",
                }
            ],
        )


def _handle_message(event: dict) -> None:
    text = extract_text_message(event)
    if not text:
        return
    line_user_id = extract_user_id(event)
    if not line_user_id:
        return
    statement_id = consume_comment_request(line_user_id)
    if not statement_id:
        statement_id = get_latest_statement_for_user(line_user_id)
    if not statement_id:
        return
    child_key = get_child_for_line_user(line_user_id)
    update_statement_reply(
        statement_id,
        line_user_id,
        status="commented",
        comment=text,
        child_key=child_key,
    )


def _handle_postback(event: dict) -> None:
    line_user_id = extract_user_id(event)
    if not line_user_id:
        return
    data = (event.get("postback") or {}).get("data")
    parsed = parse_postback(data)
    if not parsed:
        return
    kind, value = parsed
    child_key = get_child_for_line_user(line_user_id)
    if kind == "approve":
        update_statement_reply(value, line_user_id, status="approved", child_key=child_key)
    elif kind == "comment_request":
        mark_comment_request(line_user_id, value)
    elif kind == "event_attend":
        record_event_response(value, line_user_id, status="attend", child_key=child_key)
    elif kind == "event_absent":
        record_event_response(value, line_user_id, status="absent", child_key=child_key)


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method.lower() != "post":
        return _json_response({"detail": "Method not allowed."}, status_code=405)
    try:
        raw_body = req.get_body()
        signature = req.headers.get("X-Line-Signature", "")
        channel_secret = _get_channel_secret()
        if not verify_signature(raw_body, signature, channel_secret):
            return _json_response({"detail": "Invalid signature."}, status_code=400)
        payload = req.get_json()
    except (ValueError, json.JSONDecodeError):
        return _json_response({"detail": "Invalid JSON payload."}, status_code=400)
    except LineMessagingConfigError as err:
        return _json_response({"detail": str(err)}, status_code=500)

    events = payload.get("events", [])
    for event in events:
        event_type = event.get("type")
        if event_type == "follow":
            _handle_follow(event)
        elif event_type == "message":
            _handle_message(event)
        elif event_type == "postback":
            _handle_postback(event)

    return _json_response({"ok": True})
