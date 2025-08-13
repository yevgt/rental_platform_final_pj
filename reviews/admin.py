from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "property", "user", "rating", "created")
    list_select_related = ("property", "user")
    search_fields = ("property__title", "user__email", "text")
    list_filter = ("rating", ("property", admin.RelatedOnlyFieldListFilter), ("user", admin.RelatedOnlyFieldListFilter))
    ordering = ("-id",)

    @admin.display(description="Created by")
    def created(self, obj):
        return getattr(obj, "created_at", None)