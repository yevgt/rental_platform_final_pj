import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from properties.models import Property, PropertyImage, validate_image_size, Listing

# If your Review model is in app 'reviews' with FK to Property and related_name='reviews'
from reviews.models import Review

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user(email="models-owner@example.com", password=None)


@pytest.mark.django_db
def test_property_str(owner):
    prop = Property.objects.create(
        title="Nice Flat",
        description="Cozy",
        location="City",
        price="1234.50",
        number_of_rooms=2,
        property_type="apartment",
        owner=owner,
        status=Property.Status.ACTIVE,
    )
    assert str(prop) == "Nice Flat (City) - $1234.50/month"


@pytest.mark.django_db
def test_property_average_rating_no_reviews(owner):
    prop = Property.objects.create(
        title="No Reviews",
        description="",
        location="Town",
        price="1000.00",
        number_of_rooms=1,
        property_type="apartment",
        owner=owner,
        status=Property.Status.ACTIVE,
    )
    assert prop.average_rating == 0
    assert prop.review_count == 0


@pytest.mark.django_db
def test_property_average_rating_with_reviews(owner):
    renter1 = User.objects.create_user(email="r1@example.com", password=None)
    renter2 = User.objects.create_user(email="r2@example.com", password=None)

    prop = Property.objects.create(
        title="With Reviews",
        description="",
        location="Town",
        price="2000.00",
        number_of_rooms=3,
        property_type="apartment",
        owner=owner,
        status=Property.Status.ACTIVE,
    )

    # Only pass universally safe fields (property, user, rating) to avoid unknown kw errors
    Review.objects.create(property=prop, user=renter1, rating=4)
    Review.objects.create(property=prop, user=renter2, rating=2)

    # Avg = (4 + 2) / 2 = 3.0
    assert prop.average_rating == pytest.approx(3.0)
    assert prop.review_count == 2


@pytest.mark.django_db
def test_property_image_clean_valid_size(owner):
    prop = Property.objects.create(
        title="Img OK",
        description="",
        location="City",
        price="900.00",
        number_of_rooms=1,
        property_type="apartment",
        owner=owner,
        status=Property.Status.ACTIVE,
    )

    # 1 MB file (under 5MB limit)
    content = b"a" * (1 * 1024 * 1024)
    upload = SimpleUploadedFile("ok.jpg", content, content_type="image/jpeg")

    img = PropertyImage(property=prop, image=upload, caption="ok", order=0)
    # Should not raise
    img.clean()


@pytest.mark.django_db
def test_property_image_clean_too_large(owner):
    prop = Property.objects.create(
        title="Img Large",
        description="",
        location="City",
        price="1200.00",
        number_of_rooms=2,
        property_type="apartment",
        owner=owner,
        status=Property.Status.ACTIVE,
    )

    # 6 MB file (over 5MB limit)
    content = b"a" * (6 * 1024 * 1024)
    upload = SimpleUploadedFile("large.jpg", content, content_type="image/jpeg")

    img = PropertyImage(property=prop, image=upload, caption="big", order=1)

    with pytest.raises(ValidationError) as ei:
        img.clean()

    assert "не должен превышать" in str(ei.value)


def test_validate_image_size_function_direct():
    small = type("F", (), {"size": 100})()
    validate_image_size(small)  # no raise

    large = type("F", (), {"size": 6 * 1024 * 1024})()
    with pytest.raises(ValidationError):
        validate_image_size(large)


@pytest.mark.django_db
def test_property_image_str(owner):
    prop = Property.objects.create(
        title="Has Image",
        description="",
        location="City",
        price="3000.00",
        number_of_rooms=2,
        property_type="apartment",
        owner=owner,
        status=Property.Status.ACTIVE,
    )
    img = PropertyImage.objects.create(
        property=prop,
        image=SimpleUploadedFile("a.jpg", b"x", content_type="image/jpeg"),
        caption="cap",
        order=2,
    )
    assert str(img) == f"Image for {prop.title}"


@pytest.mark.django_db
def test_listing_model_creation(owner):
    prop = Property.objects.create(
        title="Listed",
        description="",
        location="City",
        price=Decimal("2500.00"),
        number_of_rooms=2,
        property_type="apartment",
        owner=owner,
        status=Property.Status.ACTIVE,
    )
    listing = Listing.objects.create(property=prop, is_active=True)
    assert listing.property_id == prop.id
    assert listing.is_active is True