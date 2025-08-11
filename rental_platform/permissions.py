from rest_framework import permissions

class IsLandlord(permissions.BasePermission):
    message = "Доступ разрешён только арендодателям."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == "landlord"
        )

class IsRenter(permissions.BasePermission):
    message = "Доступ разрешён только арендаторам."

    def has_permission(self, request, view):
        return (
                request.user
                and request.user.is_authenticated
                and getattr(request.user, "role", None) == "renter"
        )

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Разрешает изменять объект только его владельцу.
    SAFE_METHODS здесь могут быть дополнительно отрезаны др. пермишенами (IsRenter/IsLandlord).
    """
    message = "Только владелец может изменять этот объект."

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return getattr(obj, "owner_id", None) == getattr(request.user, "id", None)