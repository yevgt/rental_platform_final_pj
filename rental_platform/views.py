from django.shortcuts import render

def home(request):
    links = [
        {"label": "Admin", "url": "/admin/"},
        {"label": "JWT: Obtain Token", "url": "/api/token/"},
        {"label": "JWT: Refresh Token", "url": "/api/token/refresh/"},
        {"label": "Accounts", "url": "/api/accounts/"},
        {"label": "Properties", "url": "/api/properties/"},
        {"label": "Bookings", "url": "/api/bookings/"},
        {"label": "Reviews", "url": "/api/reviews/"},
        {"label": "Analytics", "url": "/api/analytics/"},
        {"label": "Notifications", "url": "/api/notifications/"},
        {"label": "Swagger UI", "url": "/api/docs/"},
        {"label": "Redoc", "url": "/api/redoc/"},
        {"label": "OpenAPI Schema (JSON)", "url": "/api/schema/"},
        {"label": "DRF Login/Logout", "url": "/api-auth/login/"},
    ]
    return render(request, "home.html", {"links": links})