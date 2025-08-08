from django.contrib import admin
from .models import Property


class PropertyPriceRangeFilter(admin.SimpleListFilter):
    title = "Цена"
    parameter_name = "price_range"

    def lookups(self, request, model_admin):
        return (
            ("<1000", "< 1000"),
            ("1000-2000", "1000–2000"),
            ("2000-5000", "2000–5000"),
            (">5000", "> 5000"),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val == "<1000":
            return queryset.filter(price__lt=1000)
        if val == "1000-2000":
            return queryset.filter(price__gte=1000, price__lte=2000)
        if val == "2000-5000":
            return queryset.filter(price__gte=2000, price__lte=5000)
        if val == ">5000":
            return queryset.filter(price__gt=5000)
        return queryset


class RoomsCountFilter(admin.SimpleListFilter):
    title = "Комнаты"
    parameter_name = "rooms_bucket"

    def lookups(self, request, model_admin):
        return (
            ("1", "1"),
            ("2", "2"),
            ("3", "3"),
            ("4+", "4+"),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val in {"1", "2", "3"}:
            return queryset.filter(number_of_rooms=int(val))
        if val == "4+":
            return queryset.filter(number_of_rooms__gte=4)
        return queryset


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        "id", "title", "owner", "location", "price",
        "number_of_rooms", "property_type", "status", "views_count", "created_at",
    )
    list_select_related = ("owner",)
    search_fields = ("title", "description", "location", "owner__email")
    list_filter = (
        PropertyPriceRangeFilter,
        RoomsCountFilter,
        "property_type",
        "status",
        ("created_at", admin.DateFieldListFilter),
        "location",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"