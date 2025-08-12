from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError


def validate_image_size(image_field):
    # Пример мягкой валидации (можно убрать или скорректировать)
    max_mb = 5
    if image_field.size > max_mb * 1024 * 1024:
        raise ValidationError(f"Размер изображения не должен превышать {max_mb}MB.")

class Property(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Активно"
        INACTIVE = "inactive", "Неактивно"

    class PropertyType(models.TextChoices):
        APARTMENT = "apartment", "Квартира"
        HOUSE = "house", "Дом"
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

    # Главная картинка
    main_image = models.ImageField(
        upload_to="properties/main/",
        blank=True,
        null=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.location}) - ${self.price}/month"

    @property
    def average_rating(self):
        """Calculate average rating from reviews"""
        reviews = self.reviews.all()
        if reviews:
            return sum(review.rating for review in reviews) / len(reviews)
        return 0

    @property
    def review_count(self):
        """Get total number of reviews"""
        return self.reviews.count()


class PropertyImage(models.Model):
    """Additional images for properties"""

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='properties/additional/')
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=["property", "order"]),
        ]


    def __str__(self):
        return f"Image for {self.property.title}"

    def clean(self):
        if self.image:
            validate_image_size(self.image)


class Listing(models.Model):
    property = models.OneToOneField(Property, on_delete=models.CASCADE, related_name="listing")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
