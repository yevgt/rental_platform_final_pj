import io
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory

from properties.models import Property, Listing, PropertyImage
from properties.serializers import (
    PropertyImageSerializer,
    ListingSerializer,
    PropertySerializer,
    PropertyImageUploadSerializer,
    ReviewSerializer,
)

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user(email="ser-owner@example.com", password=None)


@pytest.fixture
def rf():
    return RequestFactory()


# -------------------- PropertyImageSerializer --------------------

@pytest.mark.django_db
def test_property_image_serializer_url_with_request(owner, rf):
    # Create a property and image
    prop = Property.objects.create(
        title="P1",
        description="",
        location="City",
        price="1000.00",
        number_of_rooms=1,
        property_type="apartment",
        owner=owner,
    )
    upload = SimpleUploadedFile("img.jpg", b"x", content_type="image/jpeg")
    img = PropertyImage.objects.create(property=prop, image=upload, caption="c1", order=0)

    request = rf.get("/x")  # http://testserver/x
    ser = PropertyImageSerializer(instance=img, context={"request": request})
    data = ser.data
    assert data["url"].startswith("http://testserver/")
    assert data["caption"] == "c1"
    assert "created_at" in data


@pytest.mark.django_db
def test_property_image_serializer_url_without_request(owner):
    prop = Property.objects.create(
        title="P2",
        description="",
        location="City",
        price="1000.00",
        number_of_rooms=1,
        property_type="apartment",
        owner=owner,
    )
    upload = SimpleUploadedFile("img2.jpg", b"x", content_type="image/jpeg")
    img = PropertyImage.objects.create(property=prop, image=upload, caption="", order=0)

    ser = PropertyImageSerializer(instance=img, context={})
    data = ser.data
    assert data["url"]  # relative url
    assert data["url"].startswith("/")


def test_property_image_serializer_no_image_returns_none():
    # Call the method directly with a dummy object that has no image
    class Obj:
        image = None

    ser = PropertyImageSerializer()
    assert ser.get_url(Obj()) is None


# -------------------- ListingSerializer (read-only smoke) --------------------

def test_listing_serializer_read_only_fields():
    # Ensure serializer meta is read-only (no need to hit DB)
    ser = ListingSerializer()
    assert set(ser.Meta.read_only_fields) == {"id", "is_active", "created_at", "updated_at"}


# -------------------- PropertySerializer --------------------

@pytest.mark.django_db
@pytest.mark.parametrize("status_val, expected_active", [("active", True), ("inactive", False)])
def test_property_serializer_create_creates_listing_and_owner(owner, rf, status_val, expected_active):
    req = rf.post("/api/properties/")
    req.user = owner

    payload = {
        "title": "Created",
        "description": "desc",
        "location": "Town",
        "price": "1500.00",
        "number_of_rooms": 2,
        "property_type": "apartment",
        "status": status_val,
    }
    ser = PropertySerializer(data=payload, context={"request": req})
    assert ser.is_valid(), ser.errors
    prop = ser.save()

    assert isinstance(prop, Property)
    assert prop.owner_id == owner.id
    # Listing auto-created and synced
    listing = Listing.objects.get(property=prop)
    assert listing.is_active is expected_active


@pytest.mark.django_db
def test_property_serializer_update_syncs_listing(owner, rf):
    # Create an active property and listing
    prop = Property.objects.create(
        title="U",
        description="",
        location="L",
        price="2000.00",
        number_of_rooms=3,
        property_type="apartment",
        owner=owner,
        status=Property.Status.ACTIVE,
    )
    listing = Listing.objects.create(property=prop, is_active=True)

    # Toggle to inactive
    req = rf.patch(f"/api/properties/{prop.id}/")
    req.user = owner
    ser = PropertySerializer(instance=prop, data={"status": "inactive"}, partial=True, context={"request": req})
    assert ser.is_valid(), ser.errors
    updated = ser.save()
    listing.refresh_from_db()
    assert updated.status == "inactive"
    assert listing.is_active is False

    # Toggle back to active
    ser = PropertySerializer(instance=updated, data={"status": "active"}, partial=True, context={"request": req})
    assert ser.is_valid(), ser.errors
    updated2 = ser.save()
    listing.refresh_from_db()
    assert updated2.status == "active"
    assert listing.is_active is True


@pytest.mark.django_db
def test_property_serializer_main_image_url_with_and_without_request(owner, rf):
    prop = Property.objects.create(
        title="WithMain",
        description="",
        location="C",
        price="1100.00",
        number_of_rooms=1,
        property_type="apartment",
        owner=owner,
    )
    prop.main_image = SimpleUploadedFile("main.jpg", b"y", content_type="image/jpeg")
    prop.save(update_fields=["main_image"])

    # With request -> absolute URL
    req = rf.get("/anything")
    ser = PropertySerializer(instance=prop, context={"request": req})
    data = ser.data
    assert data["main_image_url"].startswith("http://testserver/")

    # Without request -> None (per implementation)
    ser2 = PropertySerializer(instance=prop, context={})
    data2 = ser2.data
    assert data2["main_image_url"] is None


def test_property_serializer_validators():
    ser = PropertySerializer()

    with pytest.raises(Exception):
        ser.validate_price(Decimal("0"))

    with pytest.raises(Exception):
        ser.validate_price(Decimal("-1"))

    assert ser.validate_price(Decimal("0.01")) == Decimal("0.01")

    with pytest.raises(Exception):
        ser.validate_number_of_rooms(0)

    with pytest.raises(Exception):
        ser.validate_number_of_rooms(-3)

    assert ser.validate_number_of_rooms(1) == 1


# -------------------- PropertyImageUploadSerializer --------------------

def test_property_image_upload_serializer_validate_limit_and_create():
    s = PropertyImageUploadSerializer()

    # validate with <= 10 should pass
    ok_images = [object() for _ in range(3)]
    attrs = {"images": ok_images}
    assert s.validate(attrs) == attrs

    # > 10 should raise
    too_many = {"images": [object() for _ in range(11)]}
    with pytest.raises(Exception):
        s.validate(too_many)

    # create returns data unchanged
    res = s.create({"images": ["a"], "captions": ["c1"]})
    assert res == {"images": ["a"], "captions": ["c1"]}


# -------------------- ReviewSerializer --------------------

def test_review_serializer_validate_rating_and_get_booking_id():
    s = ReviewSerializer()

    # validate_rating
    assert s.validate_rating(1) == 1
    assert s.validate_rating(5) == 5
    with pytest.raises(Exception):
        s.validate_rating(0)
    with pytest.raises(Exception):
        s.validate_rating(6)

    # get_booking_id
    class Obj:
        booking_id = 123

    assert s.get_booking_id(Obj()) == 123
    assert s.get_booking_id(object()) is None