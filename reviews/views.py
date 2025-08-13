from rest_framework import viewsets, permissions, filters
from rest_framework.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Avg
from .models import Review
from .serializers import ReviewSerializer

class IsReviewOwnerOrReadOnly(permissions.BasePermission):
    message = "Only the author of a review can change or delete it."
    def has_object_permission(self, request, view, obj):
        # SAFE_METHODS (GET, HEAD, OPTIONS) are allowed to all
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user_id == getattr(request.user, "id", None)

class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsReviewOwnerOrReadOnly]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = Review.objects.select_related("property", "user")
        prop_id = self.request.query_params.get("property")
        if prop_id:
            qs = qs.filter(property_id=prop_id)

        # Filter by exact rating
        rating = self.request.query_params.get("rating")
        if rating is not None:
            try:
                qs = qs.filter(rating=int(rating))
            except ValueError:
                pass

        # Range filters
        rating_min = self.request.query_params.get("rating_min")
        if rating_min is not None:
            try:
                qs = qs.filter(rating__gte=int(rating_min))
            except ValueError:
                pass
        rating_max = self.request.query_params.get("rating_max")
        if rating_max is not None:
            try:
                qs = qs.filter(rating__lte=int(rating_max))
            except ValueError:
                pass
        return qs

    def perform_create(self, serializer):
        try:
            serializer.save()
        except IntegrityError:
            # Violation of unique_together(property, user)
            raise ValidationError({"detail": "You have already left a review for this advert.."})