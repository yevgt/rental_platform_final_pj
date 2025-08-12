import types
from types import SimpleNamespace

import pytest
from django.contrib import admin

# Импортируем тестируемые функции/класс
from analytics.admin import (
    has_field,
    AnalyticsModelAdmin,
)


# ---------- helpers ----------

class _Field:
    def __init__(self, name):
        self.name = name


def make_fake_model(field_names):
    """
    Создаёт фейковую модель с _meta.get_fields(), возвращающим поля с указанными именами.
    Достаточно для тестов методов, которые используют только имена полей.
    """
    class _Meta:
        @staticmethod
        def get_fields():
            return [_Field(n) for n in field_names]

    # Класс с _meta и читаемым __name__ для отладки
    return type("FakeModel_" + "_".join(field_names) if field_names else "FakeModelEmpty", (), {"_meta": _Meta()})


def make_admin_with_fields(field_names):
    model = make_fake_model(field_names)
    # ModelAdmin принимает (model, admin_site)
    return AnalyticsModelAdmin(model, admin.site)


# ---------- tests ----------

def test_has_field_true_false():
    model = make_fake_model(["id", "title", "views"])
    assert has_field(model, "title") is True
    assert has_field(model, "views") is True
    assert has_field(model, "unknown") is False


def test_detection_primary_text_field_ordering():
    # Берётся первый из ('query', 'term', 'title', 'name', 'keyword'), который есть в модели.
    admin_obj = make_admin_with_fields(["id", "name", "keyword", "title"])
    # title идёт раньше, чем name/keyword — должен быть выбран title
    assert admin_obj.get_primary_text_field() == "title"

    admin_obj2 = make_admin_with_fields(["id", "term", "name"])
    assert admin_obj2.get_primary_text_field() == "term"

    admin_obj3 = make_admin_with_fields(["id"])
    assert admin_obj3.get_primary_text_field() is None


def test_detection_metric_field_ordering():
    # Приоритет: ('count', 'search_count', 'views', 'views_count', 'total', 'score')
    admin_obj = make_admin_with_fields(["id", "views_count", "total", "score"])
    # из представленных 'views_count' — первый по приоритету
    assert admin_obj.get_metric_field() == "views_count"

    admin_obj2 = make_admin_with_fields(["id"])
    assert admin_obj2.get_metric_field() is None


def test_detection_date_field_ordering():
    # Приоритет: ('date', 'day', 'period', 'created_at', 'created', 'last_used_at', 'last_viewed_at')
    admin_obj = make_admin_with_fields(["id", "created", "last_used_at"])
    assert admin_obj.get_date_field() == "created"

    admin_obj2 = make_admin_with_fields(["id"])
    assert admin_obj2.get_date_field() is None


def test_detection_property_and_user_fields():
    # property-поле из ('property', 'listing', 'estate')
    # user-поле из ('user', 'owner', 'creator')
    admin_obj = make_admin_with_fields(["id", "listing", "owner"])
    assert admin_obj.get_property_field() == "listing"
    assert admin_obj.get_user_field() == "owner"

    admin_obj2 = make_admin_with_fields(["id"])
    assert admin_obj2.get_property_field() is None
    assert admin_obj2.get_user_field() is None


def test_get_list_display_variants():
    # Полный набор: property + primary + metric + date
    admin_obj = make_admin_with_fields(["id", "property", "title", "views", "created_at"])
    fields = admin_obj.get_list_display(request=None)
    # Должны появиться “колоночные” методы-коллбеки
    assert fields == ("id", "property_col", "primary_col", "metric_col", "date_col")

    # Минимальный набор — только id
    admin_min = make_admin_with_fields(["id"])
    assert admin_min.get_list_display(request=None) == ("id",)


def test_get_search_fields_variants():
    # Есть и primary-поле, и property, и user
    admin_obj = make_admin_with_fields(["id", "title", "property", "user"])
    fields = admin_obj.get_search_fields(request=None)
    assert fields == ("title", "property__title", "property__location", "user__email")

    # Ничего нет — пустой кортеж
    admin_min = make_admin_with_fields(["id"])
    assert admin_min.get_search_fields(request=None) == tuple()


def test_get_list_filter_includes_date_flags_and_relations():
    admin_obj = make_admin_with_fields([
        "id",
        "created_at",           # дата
        "is_active", "status",  # флаги
        "property", "owner",    # связи
    ])
    filters = admin_obj.get_list_filter(request=None)

    # 1) Дата- фильтр — кортеж (field_name, DateFieldListFilter)
    date_filter = next(f for f in filters if isinstance(f, tuple) and f[0] == "created_at")
    assert date_filter[1] is admin.DateFieldListFilter

    # 2) Флаги присутствуют по именам
    assert "is_active" in filters
    assert "status" in filters

    # 3) Связанные — кортежи (field_name, RelatedOnlyFieldListFilter)
    prop_filter = next(f for f in filters if isinstance(f, tuple) and f[0] == "property")
    owner_filter = next(f for f in filters if isinstance(f, tuple) and f[0] == "owner")
    assert prop_filter[1] is admin.RelatedOnlyFieldListFilter
    assert owner_filter[1] is admin.RelatedOnlyFieldListFilter

    # Вариант без полей — пусто
    admin_min = make_admin_with_fields(["id"])
    assert admin_min.get_list_filter(request=None) == tuple()


def test_get_ordering_prefers_metric_then_date_then_id():
    # С метрикой
    admin_metric = make_admin_with_fields(["id", "views"])
    assert admin_metric.get_ordering(request=None) == ("-views",)

    # Без метрики, но с датой
    admin_date = make_admin_with_fields(["id", "created_at"])
    assert admin_date.get_ordering(request=None) == ("-created_at",)

    # Ничего — по id
    admin_min = make_admin_with_fields(["id"])
    assert admin_min.get_ordering(request=None) == ("-id",)


def test_get_list_select_related_collects_property_and_user():
    admin_obj = make_admin_with_fields(["id", "listing", "creator"])
    assert admin_obj.get_list_select_related(request=None) == ("listing", "creator")

    admin_min = make_admin_with_fields(["id"])
    assert admin_min.get_list_select_related(request=None) == tuple()


def test_column_callbacks_return_values_or_none():
    obj_full = SimpleNamespace(
        property="PROP",
        listing="LIST",
        estate="EST",
        count=10,
        search_count=11,
        views=12,
        views_count=13,
        total=14,
        score=15,
        query="q",
        term="t",
        title="Title",
        name="Name",
        keyword="Key",
        date="2020-01-01",
        day="2020-01-02",
        period="2020-01",
        created_at="2020-01-03T00:00:00",
        created="2020-01-04T00:00:00",
        last_used_at="2020-01-05T00:00:00",
        last_viewed_at="2020-01-06T00:00:00",
    )
    # Модель не влияет на коллбеки — берём любую
    admin_obj = make_admin_with_fields(["id"])

    # property_col — первое встретившееся из property/listing/estate
    assert admin_obj.property_col(obj_full) == "PROP"

    # metric_col — первое встретившееся по приоритету
    assert admin_obj.metric_col(obj_full) == 10  # count

    # primary_col — первое из query/term/title/name/keyword
    assert admin_obj.primary_col(obj_full) == "q"

    # date_col — первое из date/day/period/created_at/created/last_used_at/last_viewed_at
    assert admin_obj.date_col(obj_full) == "2020-01-01"

    # Пустой объект — везде None
    obj_empty = SimpleNamespace()
    assert admin_obj.property_col(obj_empty) is None
    assert admin_obj.metric_col(obj_empty) is None
    assert admin_obj.primary_col(obj_empty) is None
    assert admin_obj.date_col(obj_empty) is None