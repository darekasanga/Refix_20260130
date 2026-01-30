import json

import azure.functions as func

from api.line_link import (
    LineLinkError,
    LineLinkExpired,
    LineLinkInvalid,
    LineLinkNotFound,
    LineLinkRevoked,
    LineLinkService,
    LineLinkUsed,
)


def _json_response(payload: dict, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(payload),
        mimetype="application/json",
        status_code=status_code,
    )


def main(req: func.HttpRequest) -> func.HttpResponse:
    service = LineLinkService()
    try:
        req_body = req.get_json()
        token = req_body.get("token")
        otp = req_body.get("otp")
        line_user_id = req_body.get("line_user_id")
        record = service.confirm(token, otp, line_user_id)
        return _json_response(
            {
                "ok": True,
                "child_key": record["child_key"],
                "linked_at": record["linked_at"],
            }
        )
    except (ValueError, json.JSONDecodeError):
        return _json_response({"detail": "Invalid JSON payload."}, status_code=400)
    except LineLinkError as err:
        if isinstance(err, (LineLinkNotFound, LineLinkInvalid)):
            status = 400
        elif isinstance(err, (LineLinkExpired, LineLinkUsed, LineLinkRevoked)):
            status = 409
        else:
            status = 400
        return _json_response({"detail": str(err) or "Error"}, status_code=status)
