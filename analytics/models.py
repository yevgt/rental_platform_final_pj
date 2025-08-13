from django.conf import settings
from django.db import models
from properties.models import Property


class ViewHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="view_history")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="view_history")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["property"]),
            models.Index(fields=["user", "property"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"View p#{self.property_id} by u#{self.user_id}"


class SearchHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True, related_name="search_history")
    search_query = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["search_query"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.search_query} ({self.user_id})"