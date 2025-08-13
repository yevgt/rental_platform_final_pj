from rest_framework import permissions

class IsLandlord(permissions.BasePermission):
    message = "Access is restricted to landlords only.."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == "landlord"
        )

class IsRenter(permissions.BasePermission):
    message = "Access is restricted to tenants only.."

    def has_permission(self, request, view):
        return (
                request.user
                and request.user.is_authenticated
                and getattr(request.user, "role", None) == "renter"
        )

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Allows only its owner to modify the object.
    SAFE_METHODS here can be additionally cut off by other permissions (IsRenter/IsLandlord).
    """
    message = "Only the owner can modify this object.."

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return getattr(obj, "owner_id", None) == getattr(request.user, "id", None)