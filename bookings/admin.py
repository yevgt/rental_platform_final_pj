from django.contrib import admin
from .models import Booking, Message


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "property", "owner_email", "user", "status", "start_date", "end_date")
    list_select_related = ("property", "property__owner", "user")
    search_fields = ("property__title", "property__location", "user__email", "property__owner__email")
    list_filter = (
        "status",
        ("start_date", admin.DateFieldListFilter),
        ("end_date", admin.DateFieldListFilter),
        ("property", admin.RelatedOnlyFieldListFilter),
        ("user", admin.RelatedOnlyFieldListFilter),
    )
    ordering = ("-start_date",)

    @admin.display(description="Владелец (email)")
    def owner_email(self, obj):
        return getattr(getattr(obj.property, "owner", None), "email", None)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "booking", "sender", "receiver", "timestamp")
    list_select_related = ("booking", "sender", "receiver")
    search_fields = ("sender__email", "receiver__email", "booking__id")
    list_filter = (
        ("booking", admin.RelatedOnlyFieldListFilter),
        ("sender", admin.RelatedOnlyFieldListFilter),
        ("receiver", admin.RelatedOnlyFieldListFilter),
    )
    ordering = ("-id",)

    @admin.display(description="Время")
    def timestamp(self, obj):
        # Поддержка разных названий поля времени
        return getattr(obj, "created_at", None) or getattr(obj, "sent_at", None)