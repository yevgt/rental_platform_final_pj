from django.conf import settings
from django.db import models

class Notification(models.Model):
    class Types(models.TextChoices):
        BOOKING_NEW = "booking_new", "Новая заявка на бронирование (для арендодателя)"
        BOOKING_CONFIRMED = "booking_confirmed", "Подтверждение бронирования (для арендатора)"
        BOOKING_REJECTED = "booking_rejected", "Отклонение бронирования (для арендатора)"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=50, choices=Types.choices)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.type} -> {self.user_id}"