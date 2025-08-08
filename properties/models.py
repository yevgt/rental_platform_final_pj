from django.conf import settings
from django.db import models

class Property(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Активно"
        INACTIVE = "inactive", "Неактивно"

    class PropertyType(models.TextChoices):
        APARTMENT = "apartment", "Квартира"
        HOUSE = "house", "Дом"
        STUDIO = "studio", "Студия"
        ROOM = "room", "Комната"
        OTHER = "other", "Другое"

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    number_of_rooms = models.PositiveIntegerField()
    property_type = models.CharField(max_length=20, choices=PropertyType.choices)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="properties")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    views_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.location})"

class Listing(models.Model):
    property = models.OneToOneField(Property, on_delete=models.CASCADE, related_name="listing")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)