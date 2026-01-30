"""
FastAPI application exposing management code issuance and validation APIs.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import secrets
import urllib.parse
import uuid
from typing import Any

import requests

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from api.admin_service import (
    AdminAuthError,
    AdminAuthService,
    AdminInvalidCredentials,
    AdminLocked,
    WifiLocalSettingsService,
)
from api.apps_service import AppsService
from api.fastapi_settings_service import FastApiSettingsService
from api.local_data_service import LocalDatasetService
from api.network_utils import is_ip_in_cidrs
from api.guardian_auth import SessionManager
from api.guardian_service import GuardianService
from api.login_management_service import LoginManagementService
from api.line_messaging import (
    EventPayload,
    LineMessagingConfigError,
    LineMessagingRequestError,
    StatementPayload,
    build_event_flex,
    build_statement_flex,
    consume_comment_request,
    extract_reply_token,
    extract_text_message,
    extract_user_id,
    get_child_for_line_user,
    get_latest_statement_for_user,
    get_line_users_for_child,
    mark_comment_request,
    parse_postback,
    push_message,
    record_event_response,
    record_message_delivery,
    record_statement_delivery,
    register_unlinked_user,
    reply_message,
    update_statement_reply,
    verify_signature,
)
from api.notify_tokens import generate_notify_token, verify_notify_token
from api.management import (
    InvalidCode,
    ManagementCodeError,
    ManagementCodeService,
    PermissionDenied,
)
from api.database import init_db

import qrcode
from qrcode.image.svg import SvgImage

app = FastAPI(title="Management Code Service")


def _load_static_html(filename: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, filename)
    with open(file_path, encoding="utf-8") as handle:
        return handle.read()


def get_service() -> ManagementCodeService:
    return ManagementCodeService()


def get_guardian_service() -> GuardianService:
    return GuardianService()


def get_session_manager() -> SessionManager:
    secret = os.environ.get("SESSION_SECRET", "dev-session-secret")
    return SessionManager(secret=secret)


def get_admin_session_manager() -> SessionManager:
    secret = os.environ.get("ADMIN_SESSION_SECRET", os.environ.get("SESSION_SECRET", "dev-admin-secret"))
    return SessionManager(secret=secret, cookie_name="admin_session", max_age_seconds=8 * 60 * 60)


def get_admin_auth_service() -> AdminAuthService:
    return AdminAuthService()


def get_wifi_settings_service() -> WifiLocalSettingsService:
    return WifiLocalSettingsService()


def get_fastapi_settings_service() -> FastApiSettingsService:
    return FastApiSettingsService()


def get_apps_service() -> AppsService:
    return AppsService()


def get_local_dataset_service() -> LocalDatasetService:
    return LocalDatasetService()


def get_login_management_service() -> LoginManagementService:
    return LoginManagementService()


def _session_or_401(
    request: Request, manager: SessionManager
) -> dict[str, Any]:
    session = manager.decode(request.cookies.get(manager.cookie_name))
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")
    return session


def _admin_session_or_401(
    request: Request, manager: SessionManager
) -> dict[str, Any]:
    session = manager.decode(request.cookies.get(manager.cookie_name))
    admin_id = session.get("admin_id")
    if not admin_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin login required")
    return session


def _admin_session_or_403(
    request: Request, manager: SessionManager
) -> dict[str, Any]:
    session = _admin_session_or_401(request, manager)
    if session.get("must_change_password"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password change required")
    return session


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _enforce_local_access(request: Request, settings: dict[str, Any]) -> None:
    if not settings.get("enabled"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Local access disabled")
    allowed_cidrs = settings.get("allowed_cidr_list") or []
    client_ip = _client_ip(request)
    if not client_ip:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unknown client")
    if client_ip in ("127.0.0.1", "::1"):
        return
    if allowed_cidrs and not is_ip_in_cidrs(client_ip, allowed_cidrs):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Outside allowed network")


def _enforce_local_mode(settings: dict[str, Any]) -> None:
    if not settings.get("local_mode"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Local mode disabled")


def _require_local_token(request: Request, settings: dict[str, Any]) -> None:
    token = request.headers.get("X-Local-Token", "")
    expected = settings.get("shared_token")
    if not expected or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid local token")


def _line_channel_secret() -> str:
    secret = os.getenv("LINE_CHANNEL_SECRET")
    if not secret:
        raise LineMessagingConfigError("LINE_CHANNEL_SECRET is required.")
    return secret


def _parse_line_template(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if "messages" in payload and isinstance(payload["messages"], list):
        return payload["messages"]
    if "message" in payload and isinstance(payload["message"], dict):
        return [payload["message"]]
    return []


def _build_line_messages(
    message_type: str,
    message_payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None, str | None]:
    if message_type == "statement":
        required = ["statement_id", "nursery_name", "target_month", "total_amount"]
        if not all(message_payload.get(key) for key in required):
            raise ValueError("statement payload requires statement_id, nursery_name, target_month, total_amount.")
        statement = StatementPayload(
            statement_id=str(message_payload["statement_id"]),
            nursery_name=str(message_payload["nursery_name"]),
            target_month=str(message_payload["target_month"]),
            total_amount=str(message_payload["total_amount"]),
        )
        return [build_statement_flex(statement)], statement.statement_id, None
    if message_type == "event":
        required = ["event_id", "title", "date"]
        if not all(message_payload.get(key) for key in required):
            raise ValueError("event payload requires event_id, title, date.")
        event = EventPayload(
            event_id=str(message_payload["event_id"]),
            title=str(message_payload["title"]),
            date=str(message_payload["date"]),
        )
        return [build_event_flex(event)], None, event.event_id
    if message_type == "template":
        messages = _parse_line_template(message_payload)
        if not messages:
            raise ValueError("template payload requires messages.")
        return messages, None, None
    raise ValueError("Invalid message_type.")


def _handle_line_follow(event: dict[str, Any]) -> None:
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


def _handle_line_message(event: dict[str, Any]) -> None:
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


def _handle_line_postback(event: dict[str, Any]) -> None:
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


class CodeRequest(BaseModel):
    code: str


class IssueRequest(BaseModel):
    issuer_code: str


class DeactivateRequest(BaseModel):
    actor_code: str
    target_code: str


class ValidationResponse(BaseModel):
    is_valid: bool
    role: str | None = None
    is_active: bool | None = None


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminChangePasswordRequest(BaseModel):
    new_password: str


class WifiLocalSettingsPayload(BaseModel):
    id: str | None = None
    site_id: str | None = None
    enabled: bool = False
    ssid: str | None = None
    local_api_base_url: str
    local_api_port: int | None = None
    allowed_cidr_list: list[str] = []
    device_shared_secret: str
    heartbeat_interval_sec: int = 15


class FastApiSettingsPayload(BaseModel):
    id: str | None = None
    enabled: bool = True
    allowed_cidr_list: list[str] = []
    shared_token: str
    local_mode: bool = True
    require_save_token: bool = True
    require_sync_token: bool = True
    require_latest_token: bool = False


class LocalDatasetPayload(BaseModel):
    payload: Any
    version_label: str
    updated_by: str
    updated_at: str | None = None


class LoginManagementPayload(BaseModel):
    entries: list[dict[str, Any]] = []


def _handle_error(err: ManagementCodeError) -> HTTPException:
    if isinstance(err, PermissionDenied):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(err) or "Forbidden"
        )
    if isinstance(err, InvalidCode):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(err) or "Invalid code"
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail=str(err) or "Bad request"
    )


@app.post("/init-master")
def initialize_master(request: CodeRequest, service: ManagementCodeService = Depends(get_service)):
    """
    Initialize the first master_admin code when none exist yet.
    Should be called only once during deployment/bootstrap.
    """
    try:
        record = service.initialize_master(request.code)
    except ManagementCodeError as err:
        raise _handle_error(err)
    return {"message": "Master admin created", "id": record["id"]}


@app.post("/codes/issue")
def issue_admin(
    payload: IssueRequest, service: ManagementCodeService = Depends(get_service)
):
    """Issue a new admin code. Requires a valid master_admin issuer_code."""
    try:
        record = service.issue_admin_code(payload.issuer_code)
    except ManagementCodeError as err:
        raise _handle_error(err)
    return {
        "admin_code": record["plain_code"],
        "id": record["id"],
        "created_by": record["created_by"],
    }


@app.post("/codes/deactivate")
def deactivate_code(
    payload: DeactivateRequest, service: ManagementCodeService = Depends(get_service)
):
    """Deactivate a management code. Only a master_admin may perform this action."""
    try:
        record = service.deactivate_code(payload.actor_code, payload.target_code)
    except ManagementCodeError as err:
        raise _handle_error(err)
    return {"id": record["id"], "is_active": bool(record["is_active"])}


@app.post("/codes/validate", response_model=ValidationResponse)
def validate_code(
    payload: CodeRequest, service: ManagementCodeService = Depends(get_service)
):
    """Validate a code before allowing access to protected APIs."""
    try:
        record = service.validate_code(payload.code)
    except InvalidCode:
        return ValidationResponse(is_valid=False, role=None, is_active=None)
    except ManagementCodeError as err:
        raise _handle_error(err)
    return ValidationResponse(is_valid=True, role=record["role"], is_active=bool(record["is_active"]))


@app.post("/admin/auth/login")
def admin_login(
    payload: AdminLoginRequest,
    response: Response,
    auth_service: AdminAuthService = Depends(get_admin_auth_service),
    session_manager: SessionManager = Depends(get_admin_session_manager),
):
    try:
        result = auth_service.authenticate(payload.username, payload.password)
    except AdminLocked as exc:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(exc))
    except AdminInvalidCredentials as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except AdminAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    session = {
        "admin_id": result.admin_id,
        "username": result.username,
        "must_change_password": result.must_change_password,
    }
    response.set_cookie(
        session_manager.cookie_name,
        session_manager.encode(session),
        httponly=True,
        samesite="lax",
    )
    return {"username": result.username, "must_change_password": result.must_change_password}


@app.post("/admin/auth/logout")
def admin_logout(
    response: Response,
    session_manager: SessionManager = Depends(get_admin_session_manager),
):
    response.delete_cookie(session_manager.cookie_name)
    return {"status": "ok"}


@app.post("/admin/auth/change-password")
def admin_change_password(
    request: Request,
    payload: AdminChangePasswordRequest,
    auth_service: AdminAuthService = Depends(get_admin_auth_service),
    session_manager: SessionManager = Depends(get_admin_session_manager),
):
    session = _admin_session_or_401(request, session_manager)
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password too short")
    auth_service.change_password(session["admin_id"], payload.new_password)
    session["must_change_password"] = False
    response = Response(content=json.dumps({"status": "ok"}), media_type="application/json")
    response.set_cookie(
        session_manager.cookie_name,
        session_manager.encode(session),
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/admin/settings/wifi-local")
def get_wifi_local_settings(
    request: Request,
    session_manager: SessionManager = Depends(get_admin_session_manager),
    service: WifiLocalSettingsService = Depends(get_wifi_settings_service),
):
    session = session_manager.decode(request.cookies.get(session_manager.cookie_name))
    if not session.get("admin_id"):
        return RedirectResponse("/admin/login", status_code=status.HTTP_302_FOUND)
    if session.get("must_change_password"):
        return RedirectResponse("/admin/change-password", status_code=status.HTTP_302_FOUND)
    accepts = request.headers.get("accept", "")
    if "text/html" in accepts and "application/json" not in accepts:
        return HTMLResponse(content=_load_static_html("admin-wifi-local.html"))
    _admin_session_or_403(request, session_manager)
    return service.get_settings()


@app.get("/admin/local-ops")
def admin_local_ops_page(
    request: Request,
    session_manager: SessionManager = Depends(get_admin_session_manager),
):
    session = session_manager.decode(request.cookies.get(session_manager.cookie_name))
    if not session.get("admin_id"):
        return RedirectResponse("/admin/login", status_code=status.HTTP_302_FOUND)
    if session.get("must_change_password"):
        return RedirectResponse("/admin/change-password", status_code=status.HTTP_302_FOUND)
    return HTMLResponse(content=_load_static_html("admin-local-ops.html"))


@app.get("/admin/settings/fastapi-local")
def get_fastapi_local_settings(
    request: Request,
    session_manager: SessionManager = Depends(get_admin_session_manager),
    service: FastApiSettingsService = Depends(get_fastapi_settings_service),
):
    session = session_manager.decode(request.cookies.get(session_manager.cookie_name))
    if not session.get("admin_id"):
        return RedirectResponse("/admin/login", status_code=status.HTTP_302_FOUND)
    if session.get("must_change_password"):
        return RedirectResponse("/admin/change-password", status_code=status.HTTP_302_FOUND)
    _admin_session_or_403(request, session_manager)
    settings = service.get_settings()
    client_ip = _client_ip(request)
    allowed = True
    if client_ip and settings.get("allowed_cidr_list"):
        allowed = is_ip_in_cidrs(client_ip, settings.get("allowed_cidr_list") or [])
    settings["client_ip"] = client_ip
    settings["client_allowed"] = allowed
    return settings


@app.put("/admin/settings/fastapi-local")
def update_fastapi_local_settings(
    request: Request,
    payload: FastApiSettingsPayload,
    session_manager: SessionManager = Depends(get_admin_session_manager),
    service: FastApiSettingsService = Depends(get_fastapi_settings_service),
):
    session = _admin_session_or_403(request, session_manager)
    updated = service.update_settings(session["admin_id"], payload.model_dump())
    return updated


@app.post("/admin/settings/fastapi-local/regenerate-token")
def regenerate_fastapi_token(
    request: Request,
    session_manager: SessionManager = Depends(get_admin_session_manager),
    service: FastApiSettingsService = Depends(get_fastapi_settings_service),
):
    session = _admin_session_or_403(request, session_manager)
    current = service.get_settings()
    current["shared_token"] = service.regenerate_token()
    updated = service.update_settings(session["admin_id"], current)
    return {"shared_token": updated["shared_token"]}


@app.get("/login-management")
def get_login_management_entries(
    service: LoginManagementService = Depends(get_login_management_service),
):
    return {"entries": service.get_entries()}


@app.get("/admin/settings/login-management")
def get_admin_login_management_entries(
    request: Request,
    session_manager: SessionManager = Depends(get_admin_session_manager),
    service: LoginManagementService = Depends(get_login_management_service),
):
    _admin_session_or_403(request, session_manager)
    return {"entries": service.get_entries()}


@app.post("/admin/settings/login-management")
def update_admin_login_management_entries(
    request: Request,
    payload: LoginManagementPayload,
    session_manager: SessionManager = Depends(get_admin_session_manager),
    service: LoginManagementService = Depends(get_login_management_service),
):
    session = _admin_session_or_403(request, session_manager)
    entries = service.update_entries(session["admin_id"], payload.entries)
    return {"entries": entries}


@app.put("/admin/settings/wifi-local")
def update_wifi_local_settings(
    request: Request,
    payload: WifiLocalSettingsPayload,
    session_manager: SessionManager = Depends(get_admin_session_manager),
    service: WifiLocalSettingsService = Depends(get_wifi_settings_service),
):
    session = _admin_session_or_403(request, session_manager)
    updated = service.update_settings(session["admin_id"], payload.model_dump())
    service.log_audit(session["admin_id"], "WIFI_LOCAL_UPDATED", {"site_id": updated.get("site_id")})
    return updated


@app.post("/admin/settings/wifi-local/test-connection")
def test_wifi_local_connection(
    request: Request,
    session_manager: SessionManager = Depends(get_admin_session_manager),
    service: WifiLocalSettingsService = Depends(get_wifi_settings_service),
):
    session = _admin_session_or_403(request, session_manager)
    settings = service.get_settings()
    base_url = settings.get("local_api_base_url")
    ok = False
    reason = "unreachable"
    try:
        res = requests.get(f"{base_url.rstrip('/')}/health", timeout=5)
        ok = res.status_code < 400
        reason = "ok" if ok else "bad_status"
    except requests.RequestException:
        ok = False
        reason = "unreachable"
    service.log_audit(
        session["admin_id"],
        "WIFI_LOCAL_TESTED",
        {"success": ok},
    )
    return {"ok": ok, "reason": reason}


@app.get("/health")
def local_health(
    request: Request,
    service: FastApiSettingsService = Depends(get_fastapi_settings_service),
):
    settings = service.get_settings()
    _enforce_local_access(request, settings)
    return {
        "ok": True,
        "mode": "wifi-local",
        "server_time": dt.datetime.utcnow().isoformat(),
    }


@app.get("/latest")
def get_latest_dataset(
    request: Request,
    fastapi_service: FastApiSettingsService = Depends(get_fastapi_settings_service),
    dataset_service: LocalDatasetService = Depends(get_local_dataset_service),
):
    settings = fastapi_service.get_settings()
    _enforce_local_access(request, settings)
    if settings.get("require_latest_token"):
        _require_local_token(request, settings)
    latest = dataset_service.get_latest()
    if not latest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No data")
    return {
        "id": latest.id,
        "version_label": latest.version_label,
        "updated_at": latest.updated_at,
        "updated_by": latest.updated_by,
        "payload": latest.payload,
    }


@app.get("/history")
def get_dataset_history(
    request: Request,
    limit: int | None = None,
    fastapi_service: FastApiSettingsService = Depends(get_fastapi_settings_service),
    dataset_service: LocalDatasetService = Depends(get_local_dataset_service),
):
    settings = fastapi_service.get_settings()
    _enforce_local_access(request, settings)
    records = dataset_service.list_history(limit=limit)
    return {
        "count": len(records),
        "records": [
            {
                "id": record.id,
                "version_label": record.version_label,
                "updated_at": record.updated_at,
                "updated_by": record.updated_by,
            }
            for record in records
        ],
    }


@app.post("/save")
def save_dataset(
    request: Request,
    payload: LocalDatasetPayload,
    fastapi_service: FastApiSettingsService = Depends(get_fastapi_settings_service),
    dataset_service: LocalDatasetService = Depends(get_local_dataset_service),
):
    settings = fastapi_service.get_settings()
    _enforce_local_access(request, settings)
    _enforce_local_mode(settings)
    if settings.get("require_save_token"):
        _require_local_token(request, settings)
    record = dataset_service.save_dataset(
        payload=payload.payload,
        version_label=payload.version_label,
        updated_by=payload.updated_by,
        updated_at=payload.updated_at,
    )
    return {
        "id": record.id,
        "version_label": record.version_label,
        "updated_at": record.updated_at,
        "updated_by": record.updated_by,
        "payload": record.payload,
    }


@app.post("/sync")
def sync_dataset(
    request: Request,
    payload: LocalDatasetPayload,
    fastapi_service: FastApiSettingsService = Depends(get_fastapi_settings_service),
    dataset_service: LocalDatasetService = Depends(get_local_dataset_service),
):
    settings = fastapi_service.get_settings()
    _enforce_local_access(request, settings)
    _enforce_local_mode(settings)
    if settings.get("require_sync_token"):
        _require_local_token(request, settings)
    record = dataset_service.save_dataset(
        payload=payload.payload,
        version_label=payload.version_label,
        updated_by=payload.updated_by,
        updated_at=payload.updated_at,
    )
    return {
        "id": record.id,
        "version_label": record.version_label,
        "updated_at": record.updated_at,
        "updated_by": record.updated_by,
        "payload": record.payload,
    }


@app.post("/line/notify")
def send_line_notification(
    request: Request,
    payload: LineNotifyRequest,
    fastapi_service: FastApiSettingsService = Depends(get_fastapi_settings_service),
):
    settings = fastapi_service.get_settings()
    _enforce_local_access(request, settings)
    if settings.get("require_sync_token"):
        _require_local_token(request, settings)
    child_id = payload.child_id.strip()
    message_type = payload.message_type.strip()
    message_payload = payload.payload or {}
    if not child_id or not message_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="child_id and message_type are required.")
    try:
        messages, statement_id, event_id = _build_line_messages(message_type, message_payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    line_user_ids = get_line_users_for_child(str(child_id))
    if not line_user_ids:
        return {"ok": True, "results": [], "detail": "No LINE users linked."}
    results = []
    for line_user_id in line_user_ids:
        status_label = "sent"
        try:
            push_message(line_user_id, messages)
        except LineMessagingRequestError:
            status_label = "failed"
        except LineMessagingConfigError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
        record_message_delivery(
            message_type=message_type,
            child_key=str(child_id),
            line_user_id=line_user_id,
            status=status_label,
            payload=message_payload,
            statement_id=statement_id,
            event_id=event_id,
        )
        if message_type == "statement":
            record_statement_delivery(
                statement_id=str(statement_id),
                child_key=str(child_id),
                line_user_id=line_user_id,
                status=status_label,
            )
        results.append({"line_user_id": line_user_id, "status": status_label})
    return {"ok": True, "results": results}


@app.post("/line/webhook")
async def handle_line_webhook(request: Request) -> JSONResponse:
    try:
        raw_body = await request.body()
        signature = request.headers.get("X-Line-Signature", "")
        channel_secret = _line_channel_secret()
        if not verify_signature(raw_body, signature, channel_secret):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature.")
        payload = await request.json()
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload.")
    except LineMessagingConfigError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    events = payload.get("events", [])
    for event in events:
        event_type = event.get("type")
        if event_type == "follow":
            _handle_line_follow(event)
        elif event_type == "message":
            _handle_line_message(event)
        elif event_type == "postback":
            _handle_line_postback(event)
    return JSONResponse({"ok": True})


@app.get("/admin/apps")
def list_admin_apps(
    request: Request,
    session_manager: SessionManager = Depends(get_admin_session_manager),
    service: AppsService = Depends(get_apps_service),
    auth_service: AdminAuthService = Depends(get_admin_auth_service),
):
    _admin_session_or_403(request, session_manager)
    apps = service.list_latest()
    admin_cache: dict[str, str] = {}
    return {
        "items": [
            {
                "app_key": app.app_key,
                "app_name": app.app_name,
                "filename": app.filename,
                "version_label": app.version_label,
                "updated_at": app.updated_at,
                "updated_by": admin_cache.setdefault(
                    app.updated_by_admin_id,
                    (auth_service.get_admin(app.updated_by_admin_id) or {}).get("username", app.updated_by_admin_id),
                ),
                "is_latest": app.is_latest,
            }
            for app in apps
        ]
    }


@app.get("/admin/apps/{app_key}/latest")
def get_admin_app_latest(
    request: Request,
    app_key: str,
    session_manager: SessionManager = Depends(get_admin_session_manager),
    service: AppsService = Depends(get_apps_service),
    auth_service: AdminAuthService = Depends(get_admin_auth_service),
):
    _admin_session_or_403(request, session_manager)
    app = service.get_latest(app_key)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")
    admin_name = (auth_service.get_admin(app.updated_by_admin_id) or {}).get("username", app.updated_by_admin_id)
    return {
        "app_key": app.app_key,
        "app_name": app.app_name,
        "filename": app.filename,
        "version_label": app.version_label,
        "updated_at": app.updated_at,
        "updated_by": admin_name,
        "is_latest": app.is_latest,
        "download_url": f"/admin/apps/{app.app_key}/download",
        "public_url": f"/apps/{app.app_key}/latest",
    }


@app.get("/admin/apps/{app_key}/download")
def download_admin_app(
    request: Request,
    app_key: str,
    session_manager: SessionManager = Depends(get_admin_session_manager),
    service: AppsService = Depends(get_apps_service),
):
    _admin_session_or_403(request, session_manager)
    app = service.get_latest(app_key)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")
    return FileResponse(app.storage_path, filename=app.filename)


@app.get("/admin/apps/{app_key}/qr")
def get_admin_app_qr(
    request: Request,
    app_key: str,
    session_manager: SessionManager = Depends(get_admin_session_manager),
    service: AppsService = Depends(get_apps_service),
):
    _admin_session_or_403(request, session_manager)
    app = service.get_latest(app_key)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")
    url = f"{request.base_url}apps/{app.app_key}/latest"
    qr = qrcode.QRCode(border=1, box_size=6)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(image_factory=SvgImage)
    return Response(content=img.to_string(), media_type="image/svg+xml")


@app.post("/admin/apps/{app_key}/upload")
async def upload_admin_app(
    request: Request,
    app_key: str,
    file: UploadFile = File(...),
    app_name: str = Form(...),
    session_manager: SessionManager = Depends(get_admin_session_manager),
    service: AppsService = Depends(get_apps_service),
    auth_service: AdminAuthService = Depends(get_admin_auth_service),
):
    session = _admin_session_or_403(request, session_manager)
    admin_name = (auth_service.get_admin(session["admin_id"]) or {}).get("username", session["admin_id"])
    content = await file.read()
    if not file.filename or not file.filename.lower().endswith(".html"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="HTML only")
    try:
        record = service.save_upload(
            app_key=app_key,
            app_name=app_name,
            filename=file.filename,
            content=content,
            admin_id=session["admin_id"],
            updated_by_label=admin_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {
        "app_key": record.app_key,
        "app_name": record.app_name,
        "filename": record.filename,
        "version_label": record.version_label,
        "updated_at": record.updated_at,
        "updated_by": admin_name,
        "is_latest": record.is_latest,
    }


@app.get("/apps/{app_key}/latest")
def serve_app_latest(
    app_key: str,
    service: AppsService = Depends(get_apps_service),
):
    app = service.get_latest(app_key)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")
    return FileResponse(app.storage_path, media_type="text/html")


@app.get("/apps/{app_key}/download")
def download_app_latest(
    app_key: str,
    service: AppsService = Depends(get_apps_service),
):
    app = service.get_latest(app_key)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")
    return FileResponse(app.storage_path, filename=app.filename)


@app.get("/admin/login")
def admin_login_page(
    request: Request,
    session_manager: SessionManager = Depends(get_admin_session_manager),
):
    session = session_manager.decode(request.cookies.get(session_manager.cookie_name))
    if session.get("admin_id"):
        if session.get("must_change_password"):
            return RedirectResponse("/admin/change-password", status_code=status.HTTP_302_FOUND)
        return RedirectResponse("/admin/local-ops", status_code=status.HTTP_302_FOUND)
    html = """
    <html lang="ja">
      <head>
        <meta charset="UTF-8" />
        <title>Admin Login</title>
        <style>
          body { font-family: sans-serif; padding: 32px; background: #f6f7fb; }
          .card { max-width: 420px; margin: 0 auto; background: #fff; padding: 24px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
          label { display: block; margin-top: 12px; }
          input { width: 100%; padding: 10px; margin-top: 6px; border-radius: 8px; border: 1px solid #ccc; }
          button { margin-top: 16px; width: 100%; padding: 12px; border: none; border-radius: 8px; background: #275efe; color: #fff; font-weight: bold; }
          .error { color: #b00020; margin-top: 12px; }
          .info { margin-top: 16px; padding: 12px; border-radius: 10px; background: #f0f4ff; border: 1px solid #d6e2ff; font-size: 13px; }
          .info code { background: #fff; padding: 2px 6px; border-radius: 6px; }
          .info ul { margin: 8px 0 0; padding-left: 18px; }
        </style>
      </head>
      <body>
        <div class="card">
          <h1>管理者ログイン</h1>
          <label>ユーザーID</label>
          <input id="username" autocomplete="username" />
          <label>パスワード</label>
          <input id="password" type="password" autocomplete="current-password" />
          <button onclick="login()">ログイン</button>
          <div id="error" class="error"></div>
          <div class="info">
            <strong>現在の管理情報</strong>
            <ul>
              <li>管理ID: <code>admin</code></li>
              <li>管理PW: <code>admin01</code></li>
              <li>管理コード (初期マスター): <code>administration012345</code></li>
            </ul>
            <div>変更済みの場合は最新の情報を使用してください。</div>
          </div>
        </div>
        <script>
          async function login() {
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const res = await fetch('/admin/auth/login', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ username, password })
            });
            if (!res.ok) {
              const data = await res.json().catch(() => ({}));
              document.getElementById('error').textContent = data.detail || 'ログインに失敗しました';
              return;
            }
            const data = await res.json();
            if (data.must_change_password) {
              window.location.href = '/admin/change-password';
            } else {
              window.location.href = '/admin/local-ops';
            }
          }
        </script>
      </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/admin/change-password")
def admin_change_password_page(
    request: Request,
    session_manager: SessionManager = Depends(get_admin_session_manager),
):
    session = session_manager.decode(request.cookies.get(session_manager.cookie_name))
    if not session.get("admin_id"):
        return RedirectResponse("/admin/login", status_code=status.HTTP_302_FOUND)
    if not session.get("must_change_password"):
        return RedirectResponse("/admin/local-ops", status_code=status.HTTP_302_FOUND)
    html = """
    <html lang="ja">
      <head>
        <meta charset="UTF-8" />
        <title>パスワード変更</title>
        <style>
          body { font-family: sans-serif; padding: 32px; background: #f6f7fb; }
          .card { max-width: 480px; margin: 0 auto; background: #fff; padding: 24px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
          input { width: 100%; padding: 10px; margin-top: 6px; border-radius: 8px; border: 1px solid #ccc; }
          button { margin-top: 16px; width: 100%; padding: 12px; border: none; border-radius: 8px; background: #275efe; color: #fff; font-weight: bold; }
          .error { color: #b00020; margin-top: 12px; }
        </style>
      </head>
      <body>
        <div class="card">
          <h1>初回パスワード変更</h1>
          <p>初回ログインのためパスワード変更が必須です。</p>
          <label>新しいパスワード</label>
          <input id="new-password" type="password" autocomplete="new-password" />
          <button onclick="changePassword()">変更する</button>
          <div id="error" class="error"></div>
        </div>
        <script>
          async function changePassword() {
            const newPassword = document.getElementById('new-password').value;
            const res = await fetch('/admin/auth/change-password', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ new_password: newPassword })
            });
            if (!res.ok) {
              const data = await res.json().catch(() => ({}));
              document.getElementById('error').textContent = data.detail || '変更に失敗しました';
              return;
            }
            window.location.href = '/admin/local-ops';
          }
        </script>
      </body>
    </html>
    """
    return HTMLResponse(content=html)


class SmsStartRequest(BaseModel):
    phone_e164: str
    purpose: str
    return_to: str | None = None


class SmsVerifyRequest(BaseModel):
    challenge_id: str
    code: str


class NotifyThreadUpsertRequest(BaseModel):
    child_id: str


class NotifyQrRequest(BaseModel):
    child_id: str
    thread_id: str


class NotifyMessageRequest(BaseModel):
    body_text: str


class LineNotifyRequest(BaseModel):
    child_id: str
    message_type: str
    payload: dict[str, Any] = {}


def _sms_pepper() -> str:
    return os.environ.get("SMS_PEPPER", "dev-sms-pepper")


def _mask_label(label: str) -> str:
    if not label:
        return "園児"
    if len(label) <= 2:
        return f"{label[0]}*"
    return f"{label[0]}*{label[-1]}"


@app.get("/login")
def guardian_login_page() -> HTMLResponse:
    html = _load_static_html("guardian-login.html")
    return HTMLResponse(content=html)


@app.post("/auth/sms/start")
def sms_start(
    request: Request,
    payload: SmsStartRequest,
    guardian_service: GuardianService = Depends(get_guardian_service),
    session_manager: SessionManager = Depends(get_session_manager),
):
    phone_e164 = payload.phone_e164.strip()
    if not phone_e164:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing phone")
    pepper = _sms_pepper()
    phone_hash = guardian_service._hash_value(phone_e164, pepper)
    recent = guardian_service.count_recent_sms_challenges(phone_hash, seconds=60)
    if recent >= 3:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")

    ttl_seconds = int(os.environ.get("SMS_TTL", "300"))
    tries_left = int(os.environ.get("SMS_MAX_TRIES", "5"))
    debug_code = os.environ.get("SMS_DEBUG_CODE")
    code = debug_code or f"{secrets.randbelow(1000000):06d}"
    challenge = guardian_service.create_sms_challenge(
        phone_e164=phone_e164,
        code=code,
        purpose=payload.purpose,
        ttl_seconds=ttl_seconds,
        tries_left=tries_left,
        pepper=pepper,
    )
    session = session_manager.decode(request.cookies.get(session_manager.cookie_name))
    if payload.return_to:
        session["return_to"] = payload.return_to
    response = JSONResponse({"challenge_id": challenge["id"], "ttl_sec": ttl_seconds})
    response.set_cookie(
        session_manager.cookie_name,
        session_manager.encode(session),
        httponly=True,
        samesite="lax",
    )
    return response


@app.post("/auth/sms/verify")
def sms_verify(
    request: Request,
    payload: SmsVerifyRequest,
    guardian_service: GuardianService = Depends(get_guardian_service),
    session_manager: SessionManager = Depends(get_session_manager),
):
    pepper = _sms_pepper()
    challenge = guardian_service.verify_sms_challenge(
        challenge_id=payload.challenge_id,
        code=payload.code,
        pepper=pepper,
    )
    if not challenge:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code")
    external_id = challenge["phone_hash"]
    display_hint = challenge.get("phone_e164")
    user = guardian_service.upsert_identity(
        provider="sms",
        external_id=external_id,
        display_hint=display_hint,
    )
    session = session_manager.decode(request.cookies.get(session_manager.cookie_name))
    session["user_id"] = user["id"]
    session.pop("oauth_state", None)
    return_to = session.pop("return_to", "/guardian-portal.html")
    response = JSONResponse({"session_ok": True, "user_id": user["id"], "return_to": return_to})
    response.set_cookie(
        session_manager.cookie_name,
        session_manager.encode(session),
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/auth/{provider}/login")
def provider_login(
    provider: str,
    request: Request,
    return_to: str | None = None,
    guardian_service: GuardianService = Depends(get_guardian_service),
    session_manager: SessionManager = Depends(get_session_manager),
):
    if provider not in {"microsoft", "apple", "google", "yahoo"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    if not os.environ.get("OAUTH_STUB_MODE"):
        html = """
        <html lang="ja">
          <head><meta charset="UTF-8"><title>ログイン準備中</title></head>
          <body style="font-family:sans-serif;padding:24px;">
            <h1>ログイン準備中</h1>
            <p>このログイン方法は現在準備中です。</p>
            <a href="/login">ログインへ戻る</a>
          </body>
        </html>
        """
        return HTMLResponse(content=html, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    external_id = f"stub-{provider}-{uuid.uuid4()}"
    user = guardian_service.upsert_identity(provider=provider, external_id=external_id, display_hint=None)
    session = session_manager.decode(request.cookies.get(session_manager.cookie_name))
    session["user_id"] = user["id"]
    response = RedirectResponse(return_to or "/guardian-portal.html", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        session_manager.cookie_name,
        session_manager.encode(session),
        httponly=True,
        samesite="lax",
    )
    return response


@app.post("/auth/logout")
def logout(session_manager: SessionManager = Depends(get_session_manager)):
    response = RedirectResponse("/guardian-portal.html", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(session_manager.cookie_name)
    return response


@app.get("/q/notify", name="notify_qr_entry")
def notify_qr_entry(
    t: str,
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager),
    guardian_service: GuardianService = Depends(get_guardian_service),
):
    secret = os.environ.get("QR_TOKEN_SECRET", "dev-qr-secret")
    try:
        payload = verify_notify_token(t, secret=secret)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    session = session_manager.decode(request.cookies.get(session_manager.cookie_name))
    if not session.get("user_id"):
        return_to = f"{request.url.path}?t={t}"
        login_url = app.url_path_for("guardian_login_page") + "?return_to=" + urllib.parse.quote(
            return_to, safe=""
        )
        return RedirectResponse(login_url, status_code=status.HTTP_302_FOUND)

    token_record = guardian_service.consume_qr_token(payload["token_id"])
    if not token_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if token_record["thread_id"] != payload["thread_id"] or token_record["child_id"] != payload["child_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    guardian_service.upsert_link(session["user_id"], payload["child_id"], "NOTIFY_QR")
    return RedirectResponse(f"/notify/{payload['thread_id']}", status_code=status.HTTP_302_FOUND)


@app.get("/notify/{thread_id}")
def notify_thread_page(
    thread_id: str,
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager),
    guardian_service: GuardianService = Depends(get_guardian_service),
):
    session = _session_or_401(request, session_manager)
    thread = guardian_service.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    link = guardian_service.get_link(session["user_id"], thread["child_id"])
    if not link:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not linked")
    guardian_service.mark_read(thread_id=thread_id, reader_type="GUARDIAN", reader_id=session["user_id"])
    messages = guardian_service.list_messages(thread_id)
    list_items = "".join(
        f"<li><strong>{msg['sender_type']}</strong>: {msg['body_text']}</li>" for msg in messages
    ) or "<li>メッセージがありません。</li>"
    html = f"""
    <html lang="ja">
      <head><meta charset="UTF-8"><title>保護者通知</title></head>
      <body style="font-family:sans-serif;padding:24px;">
        <h1>保護者通知</h1>
        <span style="display:inline-block;padding:4px 10px;border-radius:999px;background:#dcfce7;color:#15803d;">連携済み</span>
        <h2>メッセージ</h2>
        <ul>{list_items}</ul>
        <form method="post" action="/notify/{thread_id}/reply" style="margin-top:16px;">
          <textarea name="body_text" rows="4" style="width:100%;max-width:520px;"></textarea>
          <br />
          <button type="submit">返信する</button>
        </form>
      </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.post("/notify/{thread_id}/reply")
def notify_reply(
    thread_id: str,
    request: Request,
    body_text: str = Form(""),
    session_manager: SessionManager = Depends(get_session_manager),
    guardian_service: GuardianService = Depends(get_guardian_service),
):
    session = _session_or_401(request, session_manager)
    thread = guardian_service.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    link = guardian_service.get_link(session["user_id"], thread["child_id"])
    if not link:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not linked")
    body_text = body_text.strip()
    if not body_text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing body_text")
    guardian_service.add_message(
        thread_id=thread_id,
        sender_type="GUARDIAN",
        sender_id=session["user_id"],
        body_text=body_text,
    )
    return RedirectResponse(f"/notify/{thread_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/notify/{thread_id}/read")
def notify_read(
    thread_id: str,
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager),
    guardian_service: GuardianService = Depends(get_guardian_service),
):
    session = _session_or_401(request, session_manager)
    guardian_service.mark_read(thread_id=thread_id, reader_type="GUARDIAN", reader_id=session["user_id"])
    return {"status": "ok"}


@app.get("/admin/notify/threads/{thread_id}")
def admin_notify_thread_page(
    thread_id: str,
    request: Request,
    admin_session_manager: SessionManager = Depends(get_admin_session_manager),
    guardian_service: GuardianService = Depends(get_guardian_service),
):
    session = _admin_session_or_403(request, admin_session_manager)
    thread = guardian_service.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    staff_unread = guardian_service.get_unread_count(
        thread_id=thread_id,
        reader_type="STAFF",
        reader_id=session["admin_id"],
        sender_types=["GUARDIAN"],
    )
    guardian_service.mark_read(thread_id=thread_id, reader_type="STAFF", reader_id=session["admin_id"])
    messages = guardian_service.list_messages(thread_id)
    list_items = "".join(
        f"<li><strong>{msg['sender_type']}</strong>: {msg['body_text']}</li>" for msg in messages
    ) or "<li>メッセージがありません。</li>"
    html = f"""
    <html lang="ja">
      <head><meta charset="UTF-8"><title>園側通知</title></head>
      <body style="font-family:sans-serif;padding:24px;">
        <h1>園側通知</h1>
        <p>職員未読: {staff_unread}</p>
        <h2>メッセージ</h2>
        <ul>{list_items}</ul>
        <form method="post" action="/admin/notify/threads/{thread_id}/send" style="margin-top:16px;">
          <textarea name="body_text" rows="4" style="width:100%;max-width:520px;"></textarea>
          <br />
          <button type="submit">送信する</button>
        </form>
      </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.post("/admin/notify/threads/{thread_id}/send")
def admin_notify_send(
    thread_id: str,
    request: Request,
    body_text: str = Form(""),
    admin_session_manager: SessionManager = Depends(get_admin_session_manager),
    guardian_service: GuardianService = Depends(get_guardian_service),
):
    session = _admin_session_or_403(request, admin_session_manager)
    thread = guardian_service.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    body_text = body_text.strip()
    if not body_text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing body_text")
    guardian_service.add_message(
        thread_id=thread_id,
        sender_type="STAFF",
        sender_id=session["admin_id"],
        body_text=body_text,
    )
    return RedirectResponse(f"/admin/notify/threads/{thread_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/notify/threads/{thread_id}/read")
def admin_notify_read(
    thread_id: str,
    request: Request,
    admin_session_manager: SessionManager = Depends(get_admin_session_manager),
    guardian_service: GuardianService = Depends(get_guardian_service),
):
    session = _admin_session_or_403(request, admin_session_manager)
    guardian_service.mark_read(thread_id=thread_id, reader_type="STAFF", reader_id=session["admin_id"])
    return {"status": "ok"}


@app.get("/admin/children/{child_id}/notify-state")
def admin_notify_state(
    child_id: str,
    request: Request,
    admin_session_manager: SessionManager = Depends(get_admin_session_manager),
    guardian_service: GuardianService = Depends(get_guardian_service),
):
    session = _admin_session_or_403(request, admin_session_manager)
    thread = guardian_service.get_thread_by_child(child_id)
    thread_id = thread["id"] if thread else None
    linked_count = guardian_service.count_links_for_child(child_id)
    link_status = "LINKED" if linked_count > 0 else "UNLINKED"
    unread_count = 0
    last_message_at = None
    if thread_id:
        unread_count = guardian_service.get_unread_count(
            thread_id=thread_id,
            reader_type="STAFF",
            reader_id=session["admin_id"],
            sender_types=["GUARDIAN"],
        )
        last_message_at = guardian_service.get_last_message_at(thread_id)
    return {
        "child_id": child_id,
        "link_status": link_status,
        "linked_count": linked_count,
        "thread_id": thread_id,
        "unread_count": unread_count,
        "last_message_at": last_message_at,
    }


@app.post("/admin/notify/thread/upsert")
def admin_notify_thread_upsert(
    payload: NotifyThreadUpsertRequest,
    request: Request,
    admin_session_manager: SessionManager = Depends(get_admin_session_manager),
    guardian_service: GuardianService = Depends(get_guardian_service),
):
    session = _admin_session_or_403(request, admin_session_manager)
    thread = guardian_service.upsert_thread(payload.child_id, session["admin_id"])
    return {"thread_id": thread["id"]}


@app.post("/admin/notify/qr")
def admin_notify_qr(
    payload: NotifyQrRequest,
    request: Request,
    admin_session_manager: SessionManager = Depends(get_admin_session_manager),
    guardian_service: GuardianService = Depends(get_guardian_service),
):
    session = _admin_session_or_403(request, admin_session_manager)
    thread = guardian_service.get_thread(payload.thread_id)
    if not thread or thread["child_id"] != payload.child_id:
        thread = guardian_service.upsert_thread(payload.child_id, session["admin_id"])
    ttl_seconds = int(os.environ.get("QR_TOKEN_TTL", "900"))
    token_record = guardian_service.create_qr_token_record(
        thread_id=thread["id"],
        child_id=payload.child_id,
        ttl_seconds=ttl_seconds,
    )
    secret = os.environ.get("QR_TOKEN_SECRET", "dev-qr-secret")
    token = generate_notify_token(
        token_id=token_record["id"],
        thread_id=thread["id"],
        child_id=payload.child_id,
        ttl_seconds=ttl_seconds,
        secret=secret,
    )
    url = str(request.url_for("notify_qr_entry")) + f"?t={token}"
    qr = qrcode.QRCode(border=2, box_size=6)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(image_factory=SvgImage)
    svg_data = img.to_string()
    if isinstance(svg_data, bytes):
        svg_data = svg_data.decode("utf-8")
    expires_at = token_record["expires_at"]
    return {
        "qr_svg": svg_data,
        "url": url,
        "expires_at": expires_at,
    }


@app.get("/me/links")
def list_links(
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager),
    guardian_service: GuardianService = Depends(get_guardian_service),
):
    session = _session_or_401(request, session_manager)
    return {"links": guardian_service.get_links(session["user_id"])}


@app.get("/me/badge")
def badge(
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager),
    guardian_service: GuardianService = Depends(get_guardian_service),
):
    session = _session_or_401(request, session_manager)
    count = guardian_service.count_links(session["user_id"])
    return {"linked": count > 0, "count": count}


@app.get("/me/children")
def children(
    request: Request,
    format: str | None = None,
    session_manager: SessionManager = Depends(get_session_manager),
    guardian_service: GuardianService = Depends(get_guardian_service),
):
    session = _session_or_401(request, session_manager)
    children_rows = guardian_service.get_children(session["user_id"])
    payload = [
        {
            "child_id": row["child_id"],
            "display_label_masked": _mask_label(
                row.get("display_label") or row.get("external_child_id") or row["child_id"]
            ),
        }
        for row in children_rows
    ]

    wants_json = format == "json" or "application/json" in request.headers.get("accept", "")
    if wants_json:
        return payload

    items = "".join(
        f"<li>{entry['display_label_masked']}</li>" for entry in payload
    ) or "<li>紐付け済みの園児がありません。</li>"
    html = f"""
    <html lang="ja">
      <head><meta charset="UTF-8"><title>紐付け園児一覧</title></head>
      <body style="font-family:sans-serif;padding:24px;">
        <h1>紐付け園児一覧</h1>
        <ul>{items}</ul>
        <a href="/guardian-portal.html">保護者トップへ戻る</a>
      </body>
    </html>
    """
    return HTMLResponse(content=html)
