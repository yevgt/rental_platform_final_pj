import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model

from properties.admin import (
    PropertyImageInline,
    PropertyPriceRangeFilter,
    RoomsCountFilter,
    PropertyAdmin,
    PropertyImageAdmin,
    ListingAdmin,
)
from properties.models import Property, PropertyImage, Listing

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user(email="admin-owner@example.com", password=None)


@pytest.fixture
def admin_site():
    return admin.AdminSite()


@pytest.mark.django_db
def test_property_admin_config(admin_site):
    pa = PropertyAdmin(Property, admin_site)

    assert pa.list_display == (
        "id",
        "title",
        "owner",
        "location",
        "price",
        "number_of_rooms",
        "property_type",
        "status",
        "views_count",
        "created_at",
    )
    assert pa.list_select_related == ("owner",)
    assert pa.search_fields == ("title", "description", "location", "owner__email")

    # list_filter contains custom filters, strings, and a (field, DateFieldListFilter) tuple
    lf = pa.list_filter
    assert lf[0] is PropertyPriceRangeFilter
    assert lf[1] is RoomsCountFilter
    assert lf[2] == "property_type"
    assert lf[3] == "status"
    assert isinstance(lf[4], tuple) and lf[4][0] == "created_at" and lf[4][1] is admin.DateFieldListFilter
    assert lf[5] == "location"

    assert pa.ordering == ("-created_at",)
    assert pa.date_hierarchy == "created_at"

    # Inlines
    assert pa.inlines == [PropertyImageInline]


def test_property_image_inline_config():
    assert PropertyImageInline.model is PropertyImage
    assert PropertyImageInline.extra == 1
    assert PropertyImageInline.fields == ["image", "caption", "order"]


def test_property_image_admin_config(admin_site):
    pia = PropertyImageAdmin(PropertyImage, admin_site)
    assert pia.list_display == ["property", "caption", "order", "created_at"]
    assert pia.list_filter == ["created_at"]
    assert pia.search_fields == ["property__title", "caption"]
    assert pia.ordering == ["property", "order"]


def test_listing_admin_config(admin_site):
    la = ListingAdmin(Listing, admin_site)
    assert la.list_display == ("id", "property", "is_active", "created_at", "updated_at")
    assert la.list_select_related == ("property",)
    assert la.search_fields == ("property__title", "property__location")


# -------------------- PropertyPriceRangeFilter --------------------

@pytest.mark.django_db
def test_price_range_filter_lookups(admin_site):
    pa = PropertyAdmin(Property, admin_site)
    f = PropertyPriceRangeFilter(request=None, params={}, model=Property, model_admin=pa)
    assert f.lookups(None, pa) == (
        ("<1000", "< 1000"),
        ("1000-2000", "1000–2000"),
        ("2000-5000", "2000–5000"),
        (">5000", "> 5000"),
    )


@pytest.mark.django_db
def test_price_range_filter_queryset_all_branches(owner, admin_site):
    # Prices to hit each bucket
    p_lt = Property.objects.create(
        title="lt1000", description="", location="A", price="900.00",
        number_of_rooms=1, property_type="apartment", owner=owner, status="active"
    )
    p_1000_2000 = Property.objects.create(
        title="1k-2k", description="", location="A", price="1500.00",
        number_of_rooms=2, property_type="apartment", owner=owner, status="active"
    )
    p_2000_5000 = Property.objects.create(
        title="2k-5k", description="", location="A", price="3000.00",
        number_of_rooms=3, property_type="apartment", owner=owner, status="active"
    )
    p_gt = Property.objects.create(
        title="gt5000", description="", location="A", price="6000.00",
        number_of_rooms=4, property_type="apartment", owner=owner, status="active"
    )

    pa = PropertyAdmin(Property, admin_site)

    # <1000
    f = PropertyPriceRangeFilter(request=None, params={}, model=Property, model_admin=pa)
    f.value = lambda: "<1000"
    ids = set(f.queryset(None, Property.objects.all()).values_list("id", flat=True))
    assert ids == {p_lt.id}

    # 1000-2000
    f = PropertyPriceRangeFilter(request=None, params={}, model=Property, model_admin=pa)
    f.value = lambda: "1000-2000"
    ids = set(f.queryset(None, Property.objects.all()).values_list("id", flat=True))
    assert ids == {p_1000_2000.id}

    # 2000-5000
    f = PropertyPriceRangeFilter(request=None, params={}, model=Property, model_admin=pa)
    f.value = lambda: "2000-5000"
    ids = set(f.queryset(None, Property.objects.all()).values_list("id", flat=True))
    assert ids == {p_2000_5000.id}

    # >5000
    f = PropertyPriceRangeFilter(request=None, params={}, model=Property, model_admin=pa)
    f.value = lambda: ">5000"
    ids = set(f.queryset(None, Property.objects.all()).values_list("id", flat=True))
    assert ids == {p_gt.id}

    # invalid -> no filtering
    f = PropertyPriceRangeFilter(request=None, params={}, model=Property, model_admin=pa)
    f.value = lambda: "invalid"
    ids = set(f.queryset(None, Property.objects.all()).values_list("id", flat=True))
    assert ids == {p_lt.id, p_1000_2000.id, p_2000_5000.id, p_gt.id}


# -------------------- RoomsCountFilter --------------------

@pytest.mark.django_db
def test_rooms_count_filter_lookups(admin_site):
    pa = PropertyAdmin(Property, admin_site)
    f = RoomsCountFilter(request=None, params={}, model=Property, model_admin=pa)
    assert f.lookups(None, pa) == (
        ("1", "1"),
        ("2", "2"),
        ("3", "3"),
        ("4+", "4+"),
    )


@pytest.mark.django_db
def test_rooms_count_filter_queryset_all_branches(owner, admin_site):
    p1 = Property.objects.create(
        title="r1", description="", location="A", price="1000.00",
        number_of_rooms=1, property_type="apartment", owner=owner, status="active"
    )
    p2 = Property.objects.create(
        title="r2", description="", location="A", price="1000.00",
        number_of_rooms=2, property_type="apartment", owner=owner, status="active"
    )
    p3 = Property.objects.create(
        title="r3", description="", location="A", price="1000.00",
        number_of_rooms=3, property_type="apartment", owner=owner, status="active"
    )
    p4 = Property.objects.create(
        title="r4", description="", location="A", price="1000.00",
        number_of_rooms=4, property_type="apartment", owner=owner, status="active"
    )
    p5 = Property.objects.create(
        title="r5", description="", location="A", price="1000.00",
        number_of_rooms=5, property_type="apartment", owner=owner, status="active"
    )

    pa = PropertyAdmin(Property, admin_site)

    # "1"
    f = RoomsCountFilter(request=None, params={}, model=Property, model_admin=pa)
    f.value = lambda: "1"
    ids = set(f.queryset(None, Property.objects.all()).values_list("id", flat=True))
    assert ids == {p1.id}

    # "2"
    f = RoomsCountFilter(request=None, params={}, model=Property, model_admin=pa)
    f.value = lambda: "2"
    ids = set(f.queryset(None, Property.objects.all()).values_list("id", flat=True))
    assert ids == {p2.id}

    # "3"
    f = RoomsCountFilter(request=None, params={}, model=Property, model_admin=pa)
    f.value = lambda: "3"
    ids = set(f.queryset(None, Property.objects.all()).values_list("id", flat=True))
    assert ids == {p3.id}

    # "4+"
    f = RoomsCountFilter(request=None, params={}, model=Property, model_admin=pa)
    f.value = lambda: "4+"
    ids = set(f.queryset(None, Property.objects.all()).values_list("id", flat=True))
    assert ids == {p4.id, p5.id}

    # invalid -> unchanged
    f = RoomsCountFilter(request=None, params={}, model=Property, model_admin=pa)
    f.value = lambda: "X"
    ids = set(f.queryset(None, Property.objects.all()).values_list("id", flat=True))
    assert ids == {p1.id, p2.id, p3.id, p4.id, p5.id}