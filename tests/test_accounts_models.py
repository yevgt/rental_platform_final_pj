import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_create_user_with_email_and_password_sets_defaults_and_hashes_password():
    user = User.objects.create_user(
        email="USER@Example.COM",
        password="Secret123!",
        role=User.Roles.LANDLORD,  # проверим что extra_fields применяются
    )
    # email нормализуется
    assert user.email == "USER@example.com"
    # пароль установлен и хэширован
    assert user.has_usable_password()
    assert user.check_password("Secret123!")
    # дефолты для create_user
    assert user.is_staff is False
    assert user.is_superuser is False
    # роль сохранилась
    assert user.role == User.Roles.LANDLORD


@pytest.mark.django_db
def test_create_user_without_password_sets_unusable_password():
    user = User.objects.create_user(email="nopass@example.com")
    assert user.has_usable_password() is False


def test_create_user_without_email_raises_value_error():
    with pytest.raises(ValueError):
        User.objects.create_user(email=None, password="x")


@pytest.mark.django_db
def test_create_superuser_sets_flags_true():
    su = User.objects.create_superuser(
        email="admin@example.com",
        password="Admin123!"
    )
    assert su.is_staff is True
    assert su.is_superuser is True
    assert su.has_usable_password()
    assert su.check_password("Admin123!")


def test_create_superuser_with_is_staff_false_raises():
    with pytest.raises(ValueError, match="is_staff=True"):
        User.objects.create_superuser(
            email="admin2@example.com",
            password="Admin123!",
            is_staff=False,  # провоцируем ошибку
        )


def test_create_superuser_with_is_superuser_false_raises():
    with pytest.raises(ValueError, match="is_superuser=True"):
        User.objects.create_superuser(
            email="admin3@example.com",
            password="Admin123!",
            is_superuser=False,  # провоцируем ошибку
        )


@pytest.mark.parametrize(
    "first,last,expected",
    [
        ("Ivan", "Petrov", "Ivan Petrov"),
        ("Ivan", "", "Ivan"),
        ("", "Petrov", "Petrov"),
        ("", "", ""),
    ],
)
@pytest.mark.django_db
def test_user_str_and_full_name(first, last, expected):
    u = User.objects.create_user(
        email=f"{first or 'x'}.{last or 'y'}@example.com",
        password=None,
        first_name=first,
        last_name=last,
    )
    # __str__
    assert str(u) == f"{u.email} ({u.role})"
    # full_name использует strip() и работает с пустыми значениями
    assert u.full_name == expected