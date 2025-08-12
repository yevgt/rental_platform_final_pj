import pytest
from datetime import date

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.views import (
    RegisterView,
    MeView,
    ProfileUpdateView,
    PasswordChangeView,
    DeleteAccountView,
    accounts_root,
)

User = get_user_model()


def make_user(email="user@example.com", password="InitPass!234", **extra):
    data = {
        "email": email,
        "password": password,
        "first_name": extra.pop("first_name", ""),
        "last_name": extra.pop("last_name", ""),
        "role": extra.pop("role", getattr(User.Roles, "RENTER", "renter")),
        "date_of_birth": extra.pop("date_of_birth", date(1990, 1, 1)),
        **extra,
    }
    user = User.objects.create_user(
        email=data["email"],
        password=data["password"],
        first_name=data["first_name"],
        last_name=data["last_name"],
        role=data["role"],
        date_of_birth=data["date_of_birth"],
    )
    return user


@pytest.mark.django_db
class TestAccountsViews:
    def setup_method(self):
        self.factory = APIRequestFactory()

    # RegisterView

    def test_register_success(self):
        payload = {
            "first_name": "Reg",
            "last_name": "User",
            "email": "reg@example.com",
            "password": "Str0ngPass!234",
            "password_confirm": "Str0ngPass!234",
            "role": getattr(User.Roles, "LANDLORD", "landlord"),
            "date_of_birth": "1991-02-02",
        }
        req = self.factory.post("/api/accounts/register/", payload, format="json")
        resp = RegisterView.as_view()(req)
        assert resp.status_code in (status.HTTP_201_CREATED, status.HTTP_200_OK)
        assert User.objects.filter(email="reg@example.com").exists()

    def test_register_duplicate_email_returns_400(self):
        make_user(email="dup@example.com")
        payload = {
            "first_name": "X",
            "last_name": "Y",
            "email": "Dup@Example.com",
            "password": "Str0ngPass!234",
            "password_confirm": "Str0ngPass!234",
            "role": getattr(User.Roles, "RENTER", "renter"),
            "date_of_birth": "1990-01-01",
        }
        req = self.factory.post("/api/accounts/register/", payload, format="json")
        resp = RegisterView.as_view()(req)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # MeView

    def test_me_unauthenticated_returns_401(self):
        req = self.factory.get("/api/accounts/me/")
        resp = MeView.as_view()(req)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_authenticated_returns_200(self):
        u = make_user(email="me@example.com", password=None)
        req = self.factory.get("/api/accounts/me/")
        force_authenticate(req, user=u)
        resp = MeView.as_view()(req)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data.get("email") == "me@example.com"

    # ProfileUpdateView

    def test_profile_update_success(self):
        u = make_user(email="p1@example.com", first_name="Old", last_name="Name")
        payload = {"first_name": "New"}
        req = self.factory.patch("/api/accounts/profile/", payload, format="json")
        force_authenticate(req, user=u)
        resp = ProfileUpdateView.as_view()(req)
        assert resp.status_code in (status.HTTP_200_OK, status.HTTP_202_ACCEPTED)
        u.refresh_from_db()
        assert u.first_name == "New"

    def test_profile_update_email_conflict_returns_400(self):
        make_user(email="exists@example.com")
        u = make_user(email="p2@example.com")
        payload = {"email": "Exists@Example.com"}
        req = self.factory.patch("/api/accounts/profile/", payload, format="json")
        force_authenticate(req, user=u)
        resp = ProfileUpdateView.as_view()(req)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # PasswordChangeView

    def test_password_change_wrong_old_returns_400(self):
        u = make_user(email="pc1@example.com", password="OldPass!234")
        payload = {
            "old_password": "WrongPass",
            "new_password": "NewStr0ng!234",
            "new_password_confirm": "NewStr0ng!234",
        }
        req = self.factory.post("/api/accounts/change-password/", payload, format="json")
        force_authenticate(req, user=u)
        resp = PasswordChangeView.as_view()(req)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_password_change_success(self):
        u = make_user(email="pc2@example.com", password="OldPass!234")
        payload = {
            "old_password": "OldPass!234",
            "new_password": "BrandNew!23456",
            "new_password_confirm": "BrandNew!23456",
        }
        req = self.factory.post("/api/accounts/change-password/", payload, format="json")
        force_authenticate(req, user=u)
        resp = PasswordChangeView.as_view()(req)
        assert resp.status_code == status.HTTP_200_OK
        u.refresh_from_db()
        assert u.check_password("BrandNew!23456")

    # DeleteAccountView

    def test_delete_account_success(self, monkeypatch):
        u = make_user(email="del@example.com", password="Pass!234")
        import accounts.views as av

        def fake_filter(user):
            return []  # итерируемое

        monkeypatch.setattr(av.OutstandingToken.objects, "filter", fake_filter, raising=True)

        req = self.factory.delete("/api/accounts/delete/")
        force_authenticate(req, user=u)
        resp = DeleteAccountView.as_view()(req)
        assert resp.status_code == status.HTTP_200_OK
        assert not User.objects.filter(email="del@example.com").exists()

    def test_delete_account_blacklist_raises_but_user_deleted(self, monkeypatch):
        u = make_user(email="del2@example.com", password="Pass!234")
        import accounts.views as av

        def raise_filter(user):
            raise Exception("blacklist backend down")

        monkeypatch.setattr(av.OutstandingToken.objects, "filter", raise_filter, raising=True)

        req = self.factory.delete("/api/accounts/delete/")
        force_authenticate(req, user=u)
        resp = DeleteAccountView.as_view()(req)
        assert resp.status_code == status.HTTP_200_OK
        assert not User.objects.filter(email="del2@example.com").exists()

    # accounts_root

    def test_accounts_root_ok(self):
        req = self.factory.get("/api/accounts/")
        resp = accounts_root(req)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.data
        expected_keys = {
            "token_obtain_pair",
            "token_refresh",
            "login",
            "logout",
            "register",
            "me",
            "me_update",
            "change_password",
            "delete_account",
        }
        assert expected_keys.issubset(set(data.keys()))
        for k in expected_keys:
            val = data[k]
            assert isinstance(val, str)
            # DRF reverse с request возвращает абсолютный URL; поддерживаем оба варианта
            assert val.startswith("/") or val.startswith("http")