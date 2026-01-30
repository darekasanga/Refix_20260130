import azure.functions as func
import json
from ..management import ManagementCodeService, ManagementCodeError, PermissionDenied, InvalidCode

def main(req: func.HttpRequest) -> func.HttpResponse:
    service = ManagementCodeService()
    
    try:
        req_body = req.get_json()
        actor_code = req_body.get('actor_code')
        target_code = req_body.get('target_code')
        record = service.deactivate_code(actor_code, target_code)
        return func.HttpResponse(
            json.dumps({"id": record["id"], "is_active": bool(record["is_active"])}),
            mimetype="application/json",
            status_code=200
        )
    except ManagementCodeError as err:
        if isinstance(err, PermissionDenied):
            status_code = 403
        elif isinstance(err, InvalidCode):
            status_code = 401
        else:
            status_code = 400
        return func.HttpResponse(
            json.dumps({"detail": str(err) or "Error"}),
            mimetype="application/json",
            status_code=status_code
        )