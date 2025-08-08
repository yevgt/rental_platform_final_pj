from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .serializers import RegisterSerializer, UserSerializer
from .serializers import RegisterSerializer, UserSerializer
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.reverse import reverse

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

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
        "delete_account": reverse("delete-account", request=request, format=format),
    })