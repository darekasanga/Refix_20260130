import azure.functions as func
import json
from ..management import ManagementCodeService, ManagementCodeError, PermissionDenied, InvalidCode

def main(req: func.HttpRequest) -> func.HttpResponse:
    service = ManagementCodeService()
    
    try:
        req_body = req.get_json()
        code = req_body.get('code')
        record = service.initialize_master(code)
        return func.HttpResponse(
            json.dumps({"message": "Master admin created", "id": record["id"]}),
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