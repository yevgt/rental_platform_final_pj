from django.urls import path
from .views import (
    RegisterView,
    MeView,
    ProfileUpdateView,
    PasswordChangeView,
    DeleteAccountView,
    accounts_root,
)

urlpatterns = [
    path("", accounts_root, name="accounts-root"),

    path("register/", RegisterView.as_view(), name="register"),
    path("me/", MeView.as_view(), name="me"),
    path("me-update/", ProfileUpdateView.as_view(), name="me-update"),
    path("change-password/", PasswordChangeView.as_view(), name="change-password"),
    path("delete/", DeleteAccountView.as_view(), name="delete-account"),
]