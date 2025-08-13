from rest_framework import mixins, viewsets, permissions, decorators
from rest_framework.response import Response
from .models import Notification
from .serializers import NotificationSerializer

class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user).order_by("-created_at")
        is_read = self.request.query_params.get("is_read")
        if is_read is not None:
            val = str(is_read).lower()
            if val in ("1", "true", "t", "yes", "y"):
                qs = qs.filter(is_read=True)
            elif val in ("0", "false", "f", "no", "n"):
                qs = qs.filter(is_read=False)
        notif_type = self.request.query_params.get("type")
        if notif_type:
            qs = qs.filter(type=notif_type)
        return qs

    @decorators.action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notif = self.get_object()
        if notif.user != request.user:
            return Response({"detail": "No access."}, status=403)
        if not notif.is_read:
            notif.is_read = True
            notif.save(update_fields=["is_read"])
        return Response({"detail": "Notification marked as read.", "id": notif.id, "is_read": notif.is_read})

    @decorators.action(detail=False, methods=["post"])
    def read_all(self, request):
        qs = Notification.objects.filter(user=request.user, is_read=False)
        updated = qs.update(is_read=True)
        return Response({"detail": "All notifications are marked as read.", "updated": updated})