from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    # Registers the custom User model with the admin site
    list_display = ("id", "email", "first_name", "last_name", "role", "is_staff", "is_active", "date_joined", "last_login")
    list_filter = ("role", "is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("email", "first_name", "last_name",)
    readonly_fields = ("last_login", "date_joined",)
    ordering = ("email", "-date_joined",)

    fieldsets = (                                 # Layout for editing existing users
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "role", "date_of_birth", "profile_picture",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (                             # Layout for creating new users
        (None, {"classes": ("wide",), "fields": ("email", "first_name", "last_name", "role", "password1", "password2")}),
    )