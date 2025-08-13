from django.conf import settings
from django.db import models

class Notification(models.Model):
    class Types(models.TextChoices):
        BOOKING_NEW = "booking_new", "New booking request (for landlord)"
        BOOKING_CONFIRMED = "booking_confirmed", "Booking confirmation (for the tenant)"
        BOOKING_REJECTED = "booking_rejected", "Rejecting a booking (for the tenant)"
        REVIEW_NEW = "review_new", "New review"
        MESSAGE_NEW = "message_new", "New message in booking thread"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=50, choices=Types.choices)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.type} -> {self.user_id}"