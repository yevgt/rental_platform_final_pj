from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.reverse import reverse
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    ProfileUpdateSerializer,
    PasswordChangeSerializer,
)

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    """User registration endpoint"""

    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class MeView(generics.RetrieveAPIView):
    """Получение текущего пользователя."""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class ProfileUpdateView(generics.UpdateAPIView):
    """
    Обновление профиля (PUT/PATCH).
    Например: PATCH /api/accounts/profile/ {"first_name": "Ivan"}.
    """
    serializer_class = ProfileUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class PasswordChangeView(APIView):
    """
    POST /api/accounts/change-password/
    {
      "old_password": "...",
      "new_password": "...",
      "new_password_confirm": "..."
    }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Пароль успешно изменён."}, status=status.HTTP_200_OK)

class DeleteAccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        user = request.user
        # Вносим все выданные пользователю refresh-токены в blacklist (разлогин везде)
        try:
            tokens = OutstandingToken.objects.filter(user=user)
            for t in tokens:
                BlacklistedToken.objects.get_or_create(token=t)
        except Exception:
            # Даже если blacklist недоступен, всё равно удаляем аккаунт
            pass
        user.delete()
        return Response({"detail": "Аккаунт удалён, токены отозваны."}, status=status.HTTP_200_OK)

@api_view(["GET"])
@permission_classes([AllowAny])
def accounts_root(request, format=None):
    return Response({
        "token_obtain_pair": reverse("token_obtain_pair", request=request, format=format),
        "token_refresh": reverse("token_refresh", request=request, format=format),
        "login": reverse("rest_framework:login", request=request, format=format),
        "logout": reverse("rest_framework:logout", request=request, format=format),
        "register": reverse("register", request=request, format=format),
        "me": reverse("me", request=request, format=format),
        "me_update": reverse("me-update", request=request, format=format),
        "change_password": reverse("change-password", request=request, format=format),
        "delete_account": reverse("delete-account", request=request, format=format),
    })