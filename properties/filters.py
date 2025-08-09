import django_filters
from .models import Property

class PropertyFilter(django_filters.FilterSet):
    price_min = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    price_max = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    rooms_min = django_filters.NumberFilter(field_name="number_of_rooms", lookup_expr="gte")
    rooms_max = django_filters.NumberFilter(field_name="number_of_rooms", lookup_expr="lte")
    location = django_filters.CharFilter(field_name="location", lookup_expr="icontains")
    property_type = django_filters.CharFilter(field_name="property_type", lookup_expr="exact")
    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")

    class Meta:
        model = Property
        fields = [
            "price_min", "price_max",
            "rooms_min", "rooms_max",
            "location", "property_type", "status",
        ]