from django.urls import path
from .views import TopPropertiesView, PopularSearchesView
from .views import analytics_root

urlpatterns = [
    # Root для /api/analytics/ со списком кликабельных ссылок
    path("", analytics_root, name="analytics-root"),

    path("top-properties/", TopPropertiesView.as_view(), name="top-properties"),
    path("popular-searches/", PopularSearchesView.as_view(), name="popular-searches"),
]