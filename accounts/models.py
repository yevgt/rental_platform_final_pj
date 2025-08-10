from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    # ВАЖНО: принимаем email, а не username
    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    # ВАЖНО: принимаем email, а не username
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Roles(models.TextChoices):
        RENTER = "renter", "Арендатор"
        LANDLORD = "landlord", "Арендодатель"

    #используем email вместо username
    username = None
    email = models.EmailField(unique=True)
    # name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.RENTER)

    phone_number = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]  # что дополнительно спросить при createsuperuser

    objects = UserManager()

    def __str__(self):
        return f"{self.email} ({self.role})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    class Meta:
        db_table = 'auth_user'

# from django.contrib.auth.models import AbstractUser
# from django.contrib.auth.base_user import BaseUserManager
# from django.db import models
#
#
# class User(AbstractUser):
#     class Roles(models.TextChoices):
#         RENTER = "renter", "Арендатор"
#         LANDLORD = "landlord", "Арендодатель"
#
#     # Используем email как логин
#     USERNAME_FIELD = "email"
#     REQUIRED_FIELDS = []  # можно добавить ["name"] если хотите требовать имя при createsuperuser
#
#     name = models.CharField(max_length=255, blank=True)
#     email = models.EmailField(unique=True)
#     role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.RENTER)
#
#     def save(self, *args, **kwargs):
#         # Упростим: используем email как username для входа через JWT
#         if not self.username:
#             self.username = self.email
#         super().save(*args, **kwargs)
#
#     def get_username(self):
#         # Для DRF browsable API после логина будет показано имя, если задано
#         return self.name or self.username or self.email
#
#     def __str__(self):
#         return f"{self.email} ({self.role})"