from rest_framework import viewsets, permissions, filters
from .models import Review
from .serializers import ReviewSerializer

class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        qs = Review.objects.select_related("property", "user")
        prop_id = self.request.query_params.get("property")
        if prop_id:
            qs = qs.filter(property_id=prop_id)
        return qs

    def perform_create(self, serializer):
        serializer.save()