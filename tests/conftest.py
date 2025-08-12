import pytest
from accounts.models import User

@pytest.fixture
def user_factory():
    def create_user(email: str, role: str = "renter", name: str = "", password: str = "Pass12345", **extra):
        # Совместимость: игнорируем устаревшие аргументы
        extra.pop("username", None)
        extra_name = extra.pop("name", None)  # если кто-то передаст через extra

        # Разбиваем name на first_name/last_name
        full_name = extra_name or name or ""
        first_name, last_name = "", ""
        if full_name:
            parts = full_name.strip().split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

        data = dict(
            role=role,
            first_name=first_name,
            last_name=last_name,
            # Требуемое вашей моделью поле
            date_of_birth=extra.pop("date_of_birth", "1990-01-01"),
            **extra,
        )
        return User.objects.create_user(email=email, password=password, **data)
    return create_user