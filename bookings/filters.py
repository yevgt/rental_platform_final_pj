import django_filters
from .models import Booking


class BookingFilter(django_filters.FilterSet):
    """
    Фильтры для списка бронирований:
    - status: точное совпадение
    - property_id: по id объявления
    - renter_id: по id арендатора (user)
    - start_date_from / start_date_to: диапазон по start_date
    - end_date_from / end_date_to: диапазон по end_date
    """
    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")
    property_id = django_filters.NumberFilter(field_name="property__id", lookup_expr="exact")
    renter_id = django_filters.NumberFilter(field_name="user__id", lookup_expr="exact")

    start_date_from = django_filters.DateFilter(field_name="start_date", lookup_expr="gte")
    start_date_to = django_filters.DateFilter(field_name="start_date", lookup_expr="lte")
    end_date_from = django_filters.DateFilter(field_name="end_date", lookup_expr="gte")
    end_date_to = django_filters.DateFilter(field_name="end_date", lookup_expr="lte")

    class Meta:
        model = Booking
        fields = [
            "status",
            "property_id",
            "renter_id",
            "start_date_from",
            "start_date_to",
            "end_date_from",
            "end_date_to",
        ]