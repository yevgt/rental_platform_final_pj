import logging
import json
import time
from django.utils.deprecation import MiddlewareMixin

requests_logger = logging.getLogger("requests")
fallback_logger = logging.getLogger(__name__)

SENSITIVE_PATHS = (
    "/api/token/",
    "/api/token/refresh/",
    "/api/accounts/register/",
)

class RequestLogMiddleware(MiddlewareMixin):
    """
    Logs incoming requests and responses:
    - method, path, status, user, duration, query string
    - does not log body and tokens, excludes sensitive paths
    """

    def process_request(self, request):
        request._start_time = time.time()

    def process_response(self, request, response):
        try:
            start = getattr(request, "_start_time", None)
            duration_ms = int((time.time() - start) * 1000) if start else None

            path = request.path

            # Skip statics/admin and other uninteresting paths
            if path.startswith("/static/") or path.startswith("/admin/"):
                return response

            is_sensitive = path.startswith(SENSITIVE_PATHS)

            user_id = getattr(getattr(request, "user", None), "id", None)
            user_repr = f"user_id={user_id}" if user_id else "anon"
            status = getattr(response, "status_code", "-")

            if is_sensitive:
                # Short log for sensitive endpoints
                requests_logger.info(
                    "HTTP %s %s -> %s [%s] %sms",
                    request.method,
                    path,
                    status,
                    user_repr,
                    duration_ms if duration_ms is not None else "-",
                )
            else:
                # Detailed log as JSON in one line
                payload = {
                    "method": request.method,
                    "path": path,
                    "status": status,
                    "user": user_repr,
                    "duration_ms": duration_ms,
                    "query": request.META.get("QUERY_STRING", ""),
                }
                requests_logger.info(json.dumps(payload, ensure_ascii=False))
        except Exception as e:
            # Never break a response due to logging
            fallback_logger.warning("Failed to log request/response: %s", e)
        return response
