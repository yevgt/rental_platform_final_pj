from django.conf import settings
from django.db import models
from properties.models import Property

class Review(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("property", "user")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Review {self.rating} by {self.user_id} on {self.property_id}"