import pytest
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from accounts.serializers import (
    _validate_date_of_birth,
    UserSerializer,
    RegisterSerializer,
    ProfileUpdateSerializer,
    PasswordChangeSerializer,
)

User = get_user_model()


# ---------- Helpers ----------

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


# ---------- _validate_date_of_birth ----------

def test_validate_dob_none_raises():
    with pytest.raises(Exception) as e:
        _validate_date_of_birth(None)
    assert "Дата рождения обязательна" in str(e.value)


def test_validate_dob_future_raises():
    future = timezone.now().date() + timedelta(days=1)
    with pytest.raises(Exception) as e:
        _validate_date_of_birth(future)
    assert "в будущем" in str(e.value)


def test_validate_dob_underage_raises():
    today = timezone.now().date()
    # 17 лет и 364 дня
    dob = date(today.year - 17, today.month, today.day) - timedelta(days=1)
    with pytest.raises(Exception) as e:
        _validate_date_of_birth(dob)
    assert "18+" in str(e.value)


def test_validate_dob_ok():
    today = timezone.now().date()
    dob = date(today.year - 20, today.month, today.day)
    assert _validate_date_of_birth(dob) == dob


# ---------- UserSerializer ----------

@pytest.mark.django_db
def test_user_serializer_outputs_fields():
    u = make_user(email="s1@example.com", password=None, first_name="A", last_name="B")
    s = UserSerializer(instance=u)
    data = s.data
    # Поля присутствуют
    for f in ["id", "first_name", "last_name", "email", "role", "phone_number", "profile_picture", "date_of_birth"]:
        assert f in data
    assert data["email"] == "s1@example.com"
    assert data["first_name"] == "A"
    assert data["last_name"] == "B"


# ---------- RegisterSerializer ----------

@pytest.mark.django_db
def test_register_duplicate_email_raises():
    make_user(email="dup@example.com")
    payload = {
        "first_name": "X",
        "last_name": "Y",
        "email": "Dup@Example.com",  # проверка __iexact
        "password": "StrongPass!234",
        "password_confirm": "StrongPass!234",
        "role": getattr(User.Roles, "RENTER", "renter"),
        "date_of_birth": "1990-01-01",
        "phone_number": "",
    }
    s = RegisterSerializer(data=payload)
    assert s.is_valid() is False
    assert "email" in s.errors


@pytest.mark.django_db
def test_register_password_mismatch_raises():
    payload = {
        "first_name": "X",
        "last_name": "Y",
        "email": "new@example.com",
        "password": "StrongPass!234",
        "password_confirm": "StrongPass!235",
        "role": getattr(User.Roles, "RENTER", "renter"),
        "date_of_birth": "1990-01-01",
    }
    s = RegisterSerializer(data=payload)
    assert s.is_valid() is False
    assert "password_confirm" in s.errors


@pytest.mark.django_db
def test_register_weak_password_raises():
    payload = {
        "first_name": "X",
        "last_name": "Y",
        "email": "new2@example.com",
        "password": "short",
        "password_confirm": "short",
        "role": getattr(User.Roles, "RENTER", "renter"),
        "date_of_birth": "1990-01-01",
    }
    s = RegisterSerializer(data=payload)
    assert s.is_valid() is False
    # validate_password обычно возвращает ошибку валидатора длины
    assert "password" in s.errors or "__all__" in s.errors or "non_field_errors" in s.errors


@pytest.mark.django_db
def test_register_success_creates_user():
    payload = {
        "first_name": "Reg",
        "last_name": "User",
        "email": "reg@example.com",
        "password": "Str0ngPass!234",
        "password_confirm": "Str0ngPass!234",
        "role": getattr(User.Roles, "LANDLORD", "landlord"),
        "date_of_birth": "1991-02-02",
        "phone_number": "+123",
    }
    s = RegisterSerializer(data=payload)
    assert s.is_valid(), s.errors
    user = s.save()
    assert user.id is not None
    assert user.email == "reg@example.com"
    assert user.role == getattr(User.Roles, "LANDLORD", "landlord")
    assert user.check_password("Str0ngPass!234")


# ---------- ProfileUpdateSerializer ----------

@pytest.mark.django_db
def test_profile_update_email_unchanged_ok():
    u = make_user(email="p1@example.com")
    s = ProfileUpdateSerializer(instance=u, data={"email": "p1@example.com"}, partial=True)
    assert s.is_valid(), s.errors
    u2 = s.save()
    assert u2.email == "p1@example.com"


@pytest.mark.django_db
def test_profile_update_email_taken_raises():
    make_user(email="exists@example.com")
    u = make_user(email="p2@example.com")
    s = ProfileUpdateSerializer(instance=u, data={"email": "Exists@Example.com"}, partial=True)
    assert s.is_valid() is False
    assert "email" in s.errors


@pytest.mark.django_db
def test_profile_update_invalid_role_raises():
    u = make_user(email="p3@example.com")
    s = ProfileUpdateSerializer(instance=u, data={"role": "invalid_role"}, partial=True)
    assert s.is_valid() is False
    assert "role" in s.errors


@pytest.mark.django_db
def test_profile_update_dob_future_raises():
    u = make_user(email="p4@example.com")
    future = (timezone.now().date() + timedelta(days=1)).isoformat()
    s = ProfileUpdateSerializer(instance=u, data={"date_of_birth": future}, partial=True)
    assert s.is_valid() is False
    assert "date_of_birth" in s.errors


@pytest.mark.django_db
def test_profile_update_success():
    u = make_user(email="p5@example.com", first_name="Old", last_name="Name", phone_number="")
    payload = {
        "first_name": "New",
        "last_name": "Name2",
        "phone_number": "+999",
    }
    s = ProfileUpdateSerializer(instance=u, data=payload, partial=True)
    assert s.is_valid(), s.errors
    saved = s.save()
    assert saved.first_name == "New"
    assert saved.last_name == "Name2"
    assert saved.phone_number == "+999"


# ---------- PasswordChangeSerializer ----------

@pytest.mark.django_db
def test_password_change_wrong_old_raises():
    u = make_user(email="pc1@example.com", password="OldPass!234")
    factory = APIRequestFactory()
    request = factory.post("/password-change/")
    request.user = u
    s = PasswordChangeSerializer(
        data={
            "old_password": "WrongPass",
            "new_password": "NewStr0ng!234",
            "new_password_confirm": "NewStr0ng!234",
        },
        context={"request": request},
    )
    assert s.is_valid() is False
    assert "old_password" in s.errors


@pytest.mark.django_db
def test_password_change_mismatch_raises():
    u = make_user(email="pc2@example.com", password="OldPass!234")
    factory = APIRequestFactory()
    request = factory.post("/password-change/")
    request.user = u
    s = PasswordChangeSerializer(
        data={
            "old_password": "OldPass!234",
            "new_password": "NewStr0ng!234",
            "new_password_confirm": "Different!234",
        },
        context={"request": request},
    )
    assert s.is_valid() is False
    assert "new_password_confirm" in s.errors


@pytest.mark.django_db
def test_password_change_weak_password_raises():
    u = make_user(email="pc3@example.com", password="OldPass!234")
    factory = APIRequestFactory()
    request = factory.post("/password-change/")
    request.user = u
    s = PasswordChangeSerializer(
        data={
            "old_password": "OldPass!234",
            "new_password": "short",
            "new_password_confirm": "short",
        },
        context={"request": request},
    )
    assert s.is_valid() is False
    # Валидатор пароля может вернуть ошибку в "__all__"/"non_field_errors"
    assert "new_password" in s.errors or "__all__" in s.errors or "non_field_errors" in s.errors


@pytest.mark.django_db
def test_password_change_success():
    u = make_user(email="pc4@example.com", password="OldPass!234")
    factory = APIRequestFactory()
    request = factory.post("/password-change/")
    request.user = u
    s = PasswordChangeSerializer(
        data={
            "old_password": "OldPass!234",
            "new_password": "BrandNew!23456",
            "new_password_confirm": "BrandNew!23456",
        },
        context={"request": request},
    )
    assert s.is_valid(), s.errors
    user_saved = s.save()
    assert user_saved.check_password("BrandNew!23456")