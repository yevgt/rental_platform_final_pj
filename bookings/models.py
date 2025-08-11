from django.conf import settings
from django.db import models
from properties.models import Property
from django.core.exceptions import ValidationError
from django.utils import timezone

class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает подтверждения"
        CONFIRMED = "confirmed", "Подтверждено"
        CANCELLED = "cancelled", "Отменено"
        COMPLETED = "completed", "Завершено"
        REJECTED = "rejected", "Отклонено"

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="bookings")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings") # user
    start_date = models.DateField()
    end_date = models.DateField()
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    cancel_until = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "end_date"]),  # ускоряет автозавершение
        ]

    def __str__(self):
        return f"Booking #{self.id} {self.property_id} by {self.user_id} [{self.status}]"

    def can_cancel(self, today=None):
        today = today or timezone.now().date()
        if self.status not in [self.Status.PENDING, self.Status.CONFIRMED]:
            return False
        if today >= self.start_date:
            return False
        if self.cancel_until and today > self.cancel_until:
            return False
        return True

    def mark_completed(self, commit=True):
        """Отметить бронирование завершённым, если оно подтверждено и end_date в прошлом."""
        if self.status != self.Status.CONFIRMED:
            return False
        today = timezone.now().date()
        if self.end_date >= today:
            return False
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        if commit:
            self.save(update_fields=["status", "completed_at"])
        return True

class Message(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_messages")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Msg b#{self.booking_id} from {self.sender_id} to {self.receiver_id}"