from django.urls import path
from .views import RegisterView, MeView, DeleteAccountView
from .views import accounts_root

urlpatterns = [
    # Root для /api/accounts/ со списком кликабельных ссылок
    path("", accounts_root, name="accounts-root"),

    path("register/", RegisterView.as_view(), name="register"),
    path("me/", MeView.as_view(), name="me"),
    path("delete/", DeleteAccountView.as_view(), name="delete-account"),
]