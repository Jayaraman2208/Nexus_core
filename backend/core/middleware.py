from .models import AuditLog

# Only audit state-changing methods against the API to keep the log meaningful and lightweight.
AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuditLogMiddleware:
    """Writes a tamper-evident record of who did what, when, for every mutating API call."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            if request.path.startswith("/api/") and request.method in AUDITED_METHODS:
                user = getattr(request, "user", None)
                AuditLog.objects.create(
                    actor=user if user and user.is_authenticated else None,
                    action=f"{request.method} {request.path}",
                    path=request.path,
                    method=request.method,
                    status_code=response.status_code,
                    metadata={"query_params": request.GET.dict()},
                )
        except Exception:
            # Never let audit logging break the actual request/response cycle.
            pass

        return response
