from django.conf import settings
from django.db import models
from django.db.models import Q
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
        indexes = [
            models.Index(fields=["property", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(rating__gte=1) & Q(rating__lte=5),
                name="review_rating_between_1_5",
            )
        ]

    def __str__(self):
        return f"Review {self.rating} by {self.user_id} on {self.property_id}"