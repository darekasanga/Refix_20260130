import json

import azure.functions as func

from api.line_messaging import (
    EventPayload,
    LineMessagingRequestError,
    StatementPayload,
    build_event_flex,
    build_statement_flex,
    get_line_users_for_child,
    push_message,
    record_message_delivery,
    record_statement_delivery,
)


def _json_response(payload: dict, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(payload, ensure_ascii=False),
        mimetype="application/json",
        status_code=status_code,
    )


def _parse_messages(payload: dict) -> list[dict]:
    if "messages" in payload and isinstance(payload["messages"], list):
        return payload["messages"]
    if "message" in payload and isinstance(payload["message"], dict):
        return [payload["message"]]
    return []


def _handle_statement(payload: dict) -> tuple[list[dict], str]:
    required = ["statement_id", "nursery_name", "target_month", "total_amount"]
    if not all(payload.get(key) for key in required):
        raise ValueError("statement payload requires statement_id, nursery_name, target_month, total_amount.")
    statement = StatementPayload(
        statement_id=str(payload["statement_id"]),
        nursery_name=str(payload["nursery_name"]),
        target_month=str(payload["target_month"]),
        total_amount=str(payload["total_amount"]),
    )
    return [build_statement_flex(statement)], statement.statement_id


def _handle_event(payload: dict) -> tuple[list[dict], str]:
    required = ["event_id", "title", "date"]
    if not all(payload.get(key) for key in required):
        raise ValueError("event payload requires event_id, title, date.")
    event = EventPayload(
        event_id=str(payload["event_id"]),
        title=str(payload["title"]),
        date=str(payload["date"]),
    )
    return [build_event_flex(event)], event.event_id


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method.lower() != "post":
        return _json_response({"detail": "Method not allowed."}, status_code=405)
    try:
        payload = req.get_json()
        child_key = payload.get("child_id")
        message_type = payload.get("message_type")
        message_payload = payload.get("payload") or {}
        if not child_key or not message_type:
            return _json_response({"detail": "child_id and message_type are required."}, status_code=400)
    except (ValueError, json.JSONDecodeError):
        return _json_response({"detail": "Invalid JSON payload."}, status_code=400)

    line_user_ids = get_line_users_for_child(str(child_key))
    if not line_user_ids:
        return _json_response({"detail": "No LINE users linked.", "results": []}, status_code=200)

    results = []
    messages: list[dict]
    statement_id = None
    event_id = None
    if message_type == "statement":
        try:
            messages, statement_id = _handle_statement(message_payload)
        except ValueError as err:
            return _json_response({"detail": str(err)}, status_code=400)
    elif message_type == "event":
        try:
            messages, event_id = _handle_event(message_payload)
        except ValueError as err:
            return _json_response({"detail": str(err)}, status_code=400)
    elif message_type == "template":
        messages = _parse_messages(message_payload)
        if not messages:
            return _json_response({"detail": "template payload requires messages."}, status_code=400)
    else:
        return _json_response({"detail": "Invalid message_type."}, status_code=400)

    for line_user_id in line_user_ids:
        status = "sent"
        try:
            push_message(line_user_id, messages)
        except LineMessagingRequestError:
            status = "failed"
        record_message_delivery(
            message_type=message_type,
            child_key=str(child_key),
            line_user_id=line_user_id,
            status=status,
            payload=message_payload,
            statement_id=statement_id,
            event_id=event_id,
        )
        if message_type == "statement":
            record_statement_delivery(
                statement_id=str(statement_id),
                child_key=str(child_key),
                line_user_id=line_user_id,
                status=status,
            )
        results.append({"line_user_id": line_user_id, "status": status})

    return _json_response({"ok": True, "results": results})
