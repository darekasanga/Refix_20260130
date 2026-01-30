import json

import azure.functions as func

from api.line_link import LineLinkError, LineLinkService


def _json_response(payload: dict, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(payload),
        mimetype="application/json",
        status_code=status_code,
    )


def _build_link_url(req: func.HttpRequest, token: str) -> str:
    host = req.headers.get("x-forwarded-host") or req.headers.get("host")
    proto = req.headers.get("x-forwarded-proto") or "https"
    if host:
        return f"{proto}://{host}/parent-link.html?token={token}"
    return f"/parent-link.html?token={token}"


def main(req: func.HttpRequest) -> func.HttpResponse:
    service = LineLinkService()
    try:
        if req.method.lower() == "get":
            child_key = req.params.get("child_key")
            if not child_key:
                return _json_response({"detail": "child_key is required."}, status_code=400)
            record = service.get_active_issue(child_key)
            return _json_response({"item": record})

        req_body = req.get_json()
        child_key = req_body.get("child_key")
        record = service.issue(child_key)
        return _json_response(
            {
                "issue_id": record.id,
                "token": record.token,
                "otp": record.otp,
                "expires_at": record.expires_at,
                "issued_at": record.issued_at,
                "link_url": _build_link_url(req, record.token),
            }
        )
    except (ValueError, json.JSONDecodeError):
        return _json_response({"detail": "Invalid JSON payload."}, status_code=400)
    except LineLinkError as err:
        return _json_response({"detail": str(err) or "Error"}, status_code=400)
