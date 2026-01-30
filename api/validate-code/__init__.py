import azure.functions as func
import json
from ..management import ManagementCodeService, ManagementCodeError, InvalidCode

def main(req: func.HttpRequest) -> func.HttpResponse:
    service = ManagementCodeService()
    
    try:
        req_body = req.get_json()
        code = req_body.get('code')
        record = service.validate_code(code)
        return func.HttpResponse(
            json.dumps({
                "is_valid": True,
                "role": record["role"],
                "is_active": bool(record["is_active"])
            }),
            mimetype="application/json",
            status_code=200
        )
    except InvalidCode:
        return func.HttpResponse(
            json.dumps({"is_valid": False, "role": None, "is_active": None}),
            mimetype="application/json",
            status_code=200
        )
    except ManagementCodeError as err:
        return func.HttpResponse(
            json.dumps({"detail": str(err) or "Error"}),
            mimetype="application/json",
            status_code=400
        )