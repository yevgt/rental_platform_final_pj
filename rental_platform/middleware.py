import logging
import time
from django.utils.deprecation import MiddlewareMixin

requests_logger = logging.getLogger("requests")

SENSITIVE_PATHS = (
    "/api/token/",
    "/api/token/refresh/",
    "/api/accounts/register/",
)

class RequestLogMiddleware(MiddlewareMixin):
    """
    Логирует входящие запросы и ответы:
    - метод, путь, статус, пользователь, длительность, query string
    - не логирует тело и токены, исключает чувствительные пути
    """

    def process_request(self, request):
        request._start_time = time.time()

    def process_response(self, request, response):
        try:
            duration_ms = None
            if hasattr(request, "_start_time"):
                duration_ms = int((time.time() - request._start_time) * 1000)

            path = request.path
            # Пропускаем статику/админку и др. неинтересные пути
            if path.startswith("/static/") or path.startswith("/admin/"):
                return response

            # Не логируем чувствительные эндпоинты подробно
            is_sensitive = path.startswith(SENSITIVE_PATHS)

            user_id = getattr(getattr(request, "user", None), "id", None)
            user_repr = f"user_id={user_id}" if user_id else "anon"

            msg = {
                "method": request.method,
                "path": path,
                "status": getattr(response, "status_code", "-"),
                "user": user_repr,
                "duration_ms": duration_ms,
                "query": request.META.get("QUERY_STRING", ""),
            }

            if is_sensitive:
                # Минимальный лог на чувствительных эндпоинтах
                requests_logger.info("request", extra={"message": str(msg)})
            else:
                requests_logger.info(f"{msg}")
        except Exception:
            # Никогда не ломаем ответ из-за логирования
            logging.getLogger(__name__).exception("Failed to log request/response")
        return response