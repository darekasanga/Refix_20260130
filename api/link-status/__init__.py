import json

import azure.functions as func

from api.line_link import LineLinkError, LineLinkService


def _json_response(payload: dict, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(payload),
        mimetype="application/json",
        status_code=status_code,
    )


def _parse_child_keys(raw: str | None) -> list[str]:
    if not raw:
        return []
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(item).strip() for item in data if str(item).strip()]
        except json.JSONDecodeError:
            return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def main(req: func.HttpRequest) -> func.HttpResponse:
    service = LineLinkService()
    try:
        child_keys = _parse_child_keys(req.params.get("child_keys"))
        if not child_keys:
            single_key = req.params.get("child_key")
            if single_key:
                child_keys = [single_key]
        items = service.get_link_status(child_keys)
        return _json_response({"items": items})
    except LineLinkError as err:
        return _json_response({"detail": str(err) or "Error"}, status_code=400)
