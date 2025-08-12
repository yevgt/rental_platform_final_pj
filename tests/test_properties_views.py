import pytest
from django.db import models as dj_models
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory, force_authenticate

import properties.views as pv
from properties.models import Property, PropertyImage, Listing
from reviews.models import Review
from analytics.models import ViewHistory, SearchHistory

User = get_user_model()


@pytest.fixture
def rf():
    return APIRequestFactory()


@pytest.fixture
def owner(db):
    return User.objects.create_user(email="landlord@example.com", password=None)


@pytest.fixture
def other(db):
    return User.objects.create_user(email="other@example.com", password=None)


class TestablePropertyViewSet(pv.PropertyViewSet):
    # Disable auth/permissions for action tests
    def get_permissions(self):
        return []

    def check_object_permissions(self, request, obj):
        return True


# -------------------- get_queryset logic (unit-level) --------------------

@pytest.mark.django_db
def test_property_viewset_get_queryset_branches(owner, other, rf):
    p1 = Property.objects.create(
        title="Owner A", description="", location="X", price="1000.00",
        number_of_rooms=1, property_type="apartment", owner=owner, status=Property.Status.ACTIVE
    )
    p2 = Property.objects.create(
        title="Other B", description="", location="Y", price="2000.00",
        number_of_rooms=2, property_type="apartment", owner=other, status=Property.Status.ACTIVE
    )

    request = rf.get("/api/properties/")
    request.user = owner

    view = pv.PropertyViewSet()
    view.request = request

    view.action = "list"
    ids = set(view.get_queryset().values_list("id", flat=True))
    assert ids == {p1.id}

    view.action = "retrieve"
    ids = set(view.get_queryset().values_list("id", flat=True))
    assert ids == {p1.id}

    view.action = "update"
    ids = set(view.get_queryset().values_list("id", flat=True))
    assert ids == {p1.id, p2.id}


# -------------------- toggle_status --------------------

@pytest.mark.django_db
def test_toggle_status_updates_listing(owner, rf):
    prop = Property.objects.create(
        title="Toggle", description="", location="C", price="900.00",
        number_of_rooms=1, property_type="apartment", owner=owner, status=Property.Status.ACTIVE
    )
    listing = Listing.objects.create(property=prop, is_active=True)

    request = rf.post(f"/api/properties/{prop.id}/toggle_status/")
    force_authenticate(request, user=owner)
    view = TestablePropertyViewSet.as_view({"post": "toggle_status"})
    resp = view(request, pk=prop.id)
    assert resp.status_code == 200
    prop.refresh_from_db()
    listing.refresh_from_db()
    assert prop.status == Property.Status.INACTIVE
    assert listing.is_active is False

    # Toggle back
    request2 = rf.post(f"/api/properties/{prop.id}/toggle_status/")
    force_authenticate(request2, user=owner)
    resp2 = view(request2, pk=prop.id)
    assert resp2.status_code == 200
    prop.refresh_from_db()
    listing.refresh_from_db()
    assert prop.status == Property.Status.ACTIVE
    assert listing.is_active is True


# -------------------- upload_images --------------------

@pytest.mark.django_db
def test_upload_images_success_and_limit(monkeypatch, owner, rf):
    # Patch missing "models" symbol in views if needed
    if not hasattr(pv, "models"):
        monkeypatch.setattr(pv, "models", dj_models, raising=False)

    prop = Property.objects.create(
        title="Imgs", description="", location="Z", price="1100.00",
        number_of_rooms=2, property_type="apartment", owner=owner, status=Property.Status.ACTIVE
    )
    # Existing with non-zero order so current_max is picked up
    PropertyImage.objects.create(
        property=prop, image=SimpleUploadedFile("e.jpg", b"e"), caption="e", order=5
    )

    file1 = SimpleUploadedFile("a.jpg", b"a", content_type="image/jpeg")
    file2 = SimpleUploadedFile("b.jpg", b"b", content_type="image/jpeg")

    request = rf.post(
        f"/api/properties/{prop.id}/upload-images/",
        {"images": [file1, file2], "captions": ["cap-a"]},
        format="multipart",
    )
    force_authenticate(request, user=owner)
    view = TestablePropertyViewSet.as_view({"post": "upload_images"})
    resp = view(request, pk=prop.id)
    assert resp.status_code == 201
    data = resp.data
    assert isinstance(data, list) and len(data) == 2

    # Orders should continue after 5 => 6 and 7
    prop_imgs = list(PropertyImage.objects.filter(property=prop).order_by("order"))
    orders = [i.order for i in prop_imgs]
    assert orders == [5, 6, 7]

    # Limit exceeded
    prop2 = Property.objects.create(
        title="Full", description="", location="Z", price="1200.00",
        number_of_rooms=2, property_type="apartment", owner=owner, status=Property.Status.ACTIVE
    )
    # Already 10 images
    for i in range(10):
        PropertyImage.objects.create(
            property=prop2, image=SimpleUploadedFile(f"f{i}.jpg", b"x"), caption="", order=i + 1
        )
    extra = SimpleUploadedFile("extra.jpg", b"x")

    request2 = rf.post(
        f"/api/properties/{prop2.id}/upload-images/",
        {"images": [extra]},
        format="multipart",
    )
    force_authenticate(request2, user=owner)
    resp2 = view(request2, pk=prop2.id)
    assert resp2.status_code == 400
    assert "Превышен общий лимит" in str(resp2.data)


# -------------------- delete_image --------------------

@pytest.mark.django_db
def test_delete_image_missing_notfound_and_success(owner, rf):
    prop = Property.objects.create(
        title="Del", description="", location="Z", price="1300.00",
        number_of_rooms=2, property_type="apartment", owner=owner, status=Property.Status.ACTIVE
    )

    view = TestablePropertyViewSet.as_view({"post": "delete_image"})

    # Missing image_id
    req1 = rf.post(f"/api/properties/{prop.id}/delete-image/", {}, format="json")
    force_authenticate(req1, user=owner)
    resp1 = view(req1, pk=prop.id)
    assert resp1.status_code == 400

    # Not found
    req2 = rf.post(f"/api/properties/{prop.id}/delete-image/", {"image_id": 9999}, format="json")
    force_authenticate(req2, user=owner)
    resp2 = view(req2, pk=prop.id)
    assert resp2.status_code == 404

    # Success
    img = PropertyImage.objects.create(
        property=prop, image=SimpleUploadedFile("d.jpg", b"x"), caption="", order=1
    )
    req3 = rf.post(f"/api/properties/{prop.id}/delete-image/", {"image_id": img.id}, format="json")
    force_authenticate(req3, user=owner)
    resp3 = view(req3, pk=prop.id)
    assert resp3.status_code == 204
    assert not PropertyImage.objects.filter(id=img.id).exists()


# -------------------- reorder_images --------------------

@pytest.mark.django_db
def test_reorder_images_valid_and_invalid(owner, rf):
    prop = Property.objects.create(
        title="Reorder", description="", location="Z", price="1400.00",
        number_of_rooms=2, property_type="apartment", owner=owner, status=Property.Status.ACTIVE
    )
    img1 = PropertyImage.objects.create(property=prop, image=SimpleUploadedFile("1.jpg", b"1"), caption="", order=3)
    img2 = PropertyImage.objects.create(property=prop, image=SimpleUploadedFile("2.jpg", b"2"), caption="", order=1)
    img3 = PropertyImage.objects.create(property=prop, image=SimpleUploadedFile("3.jpg", b"3"), caption="", order=2)

    view = TestablePropertyViewSet.as_view({"post": "reorder_images"})

    # Invalid payload
    bad = rf.post(f"/api/properties/{prop.id}/reorder-images/", {"order": ""}, format="json")
    force_authenticate(bad, user=owner)
    bad_resp = view(bad, pk=prop.id)
    assert bad_resp.status_code == 400

    # Valid partial list (img3 will be appended after)
    req = rf.post(
        f"/api/properties/{prop.id}/reorder-images/",
        {"order": [img2.id, img1.id]},
        format="json",
    )
    force_authenticate(req, user=owner)
    resp = view(req, pk=prop.id)
    assert resp.status_code == 200

    img1.refresh_from_db()
    img2.refresh_from_db()
    img3.refresh_from_db()
    assert (img2.order, img1.order, img3.order) == (1, 2, 3)


# -------------------- update_image_caption --------------------

@pytest.mark.django_db
def test_update_image_caption_branches(owner, rf):
    prop = Property.objects.create(
        title="Cap", description="", location="Z", price="1500.00",
        number_of_rooms=2, property_type="apartment", owner=owner, status=Property.Status.ACTIVE
    )

    view = TestablePropertyViewSet.as_view({"post": "update_image_caption"})

    # Missing id
    req1 = rf.post(f"/api/properties/{prop.id}/update-image-caption/", {"caption": "x"}, format="json")
    force_authenticate(req1, user=owner)
    resp1 = view(req1, pk=prop.id)
    assert resp1.status_code == 400

    # Not found
    req2 = rf.post(f"/api/properties/{prop.id}/update-image-caption/", {"image_id": 9999, "caption": "x"}, format="json")
    force_authenticate(req2, user=owner)
    resp2 = view(req2, pk=prop.id)
    assert resp2.status_code == 404

    # Success
    img = PropertyImage.objects.create(
        property=prop, image=SimpleUploadedFile("c.jpg", b"x"), caption="", order=1
    )
    req3 = rf.post(
        f"/api/properties/{prop.id}/update-image-caption/",
        {"image_id": img.id, "caption": "new"},
        format="json",
    )
    force_authenticate(req3, user=owner)
    resp3 = view(req3, pk=prop.id)
    assert resp3.status_code == 200
    img.refresh_from_db()
    assert img.caption == "new"


# -------------------- set_main_image --------------------

@pytest.mark.django_db
def test_set_main_image_all_branches(owner, rf):
    prop = Property.objects.create(
        title="Main", description="", location="Z", price="1600.00",
        number_of_rooms=2, property_type="apartment", owner=owner, status=Property.Status.ACTIVE
    )

    view = TestablePropertyViewSet.as_view({"post": "set_main_image"})

    # Neither provided
    req0 = rf.post(f"/api/properties/{prop.id}/set-main-image/", {}, format="multipart")
    force_authenticate(req0, user=owner)
    resp0 = view(req0, pk=prop.id)
    assert resp0.status_code == 400

    # Both provided -> 400
    img_any = PropertyImage.objects.create(
        property=prop, image=SimpleUploadedFile("x.jpg", b"x"), caption="", order=1
    )
    both = rf.post(
        f"/api/properties/{prop.id}/set-main-image/",
        {"image_id": img_any.id, "main_image": SimpleUploadedFile("m.jpg", b"m")},
        format="multipart",
    )
    force_authenticate(both, user=owner)
    both_resp = view(both, pk=prop.id)
    assert both_resp.status_code == 400

    # Not found ID
    notfound = rf.post(
        f"/api/properties/{prop.id}/set-main-image/",
        {"image_id": 9999},
        format="multipart",
    )
    force_authenticate(notfound, user=owner)
    nf_resp = view(notfound, pk=prop.id)
    assert nf_resp.status_code == 404

    # Use existing image by id
    use_id = rf.post(
        f"/api/properties/{prop.id}/set-main-image/",
        {"image_id": img_any.id},
        format="multipart",
    )
    force_authenticate(use_id, user=owner)
    resp_id = view(use_id, pk=prop.id)
    assert resp_id.status_code == 200
    prop.refresh_from_db()
    assert prop.main_image.name.endswith("x.jpg")
    assert resp_id.data["main_image_url"].startswith("http://testserver/")

    # Upload new file
    new = rf.post(
        f"/api/properties/{prop.id}/set-main-image/",
        {"main_image": SimpleUploadedFile("new.jpg", b"n")},
        format="multipart",
    )
    force_authenticate(new, user=owner)
    resp_new = view(new, pk=prop.id)
    assert resp_new.status_code == 200
    prop.refresh_from_db()
    assert prop.main_image.name.endswith("new.jpg")
    assert resp_new.data["main_image_url"].startswith("http://testserver/")


# -------------------- PublicPropertyViewSet --------------------

@pytest.mark.django_db
def test_public_list_filters_only_active_and_search_history(owner, rf):
    active = Property.objects.create(
        title="A", description="", location="L", price="1700.00",
        number_of_rooms=2, property_type="apartment", owner=owner, status=Property.Status.ACTIVE
    )
    inactive = Property.objects.create(
        title="I", description="", location="L", price="1800.00",
        number_of_rooms=2, property_type="apartment", owner=owner, status=Property.Status.INACTIVE
    )

    # Anonymous -> no SearchHistory, only active returned
    anon_req = rf.get("/api/properties/public/?search=foo")
    view = pv.PublicPropertyViewSet.as_view({"get": "list"})
    resp = view(anon_req)
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.data]
    assert ids == [active.id]
    assert SearchHistory.objects.count() == 0

    # Authenticated -> SearchHistory created
    auth_req = rf.get("/api/properties/public/?search=bar")
    force_authenticate(auth_req, user=owner)
    resp2 = view(auth_req)
    assert resp2.status_code == 200
    assert SearchHistory.objects.count() == 1
    sh = SearchHistory.objects.first()
    assert sh.user_id == owner.id and sh.search_query == "bar"


@pytest.mark.django_db
def test_public_retrieve_increments_views_and_view_history(owner, rf):
    prop = Property.objects.create(
        title="Pub", description="", location="L", price="1900.00",
        number_of_rooms=2, property_type="apartment", owner=owner, status=Property.Status.ACTIVE
    )

    detail_view = pv.PublicPropertyViewSet.as_view({"get": "retrieve"})

    # Anonymous
    req1 = rf.get(f"/api/properties/public/{prop.id}/")
    resp1 = detail_view(req1, pk=prop.id)
    assert resp1.status_code == 200
    prop.refresh_from_db()
    assert prop.views_count == 1
    assert ViewHistory.objects.count() == 0

    # Authenticated
    req2 = rf.get(f"/api/properties/public/{prop.id}/")
    force_authenticate(req2, user=owner)
    resp2 = detail_view(req2, pk=prop.id)
    assert resp2.status_code == 200
    prop.refresh_from_db()
    assert prop.views_count == 2
    vh = ViewHistory.objects.first()
    assert vh is not None and vh.user_id == owner.id and vh.property_id == prop.id


@pytest.mark.django_db
def test_public_reviews_returns_sorted_reviews(owner, rf):
    prop = Property.objects.create(
        title="R", description="", location="L", price="2000.00",
        number_of_rooms=2, property_type="apartment", owner=owner, status=Property.Status.ACTIVE
    )
    user1 = User.objects.create_user(email="r1@example.com", password=None)
    user2 = User.objects.create_user(email="r2@example.com", password=None)

    r1 = Review.objects.create(property=prop, user=user1, rating=3)
    r2 = Review.objects.create(property=prop, user=user2, rating=5)

    other_prop = Property.objects.create(
        title="Other", description="", location="L", price="2100.00",
        number_of_rooms=2, property_type="apartment", owner=owner, status=Property.Status.ACTIVE
    )
    Review.objects.create(property=other_prop, user=user1, rating=1)

    reviews_view = pv.PublicPropertyViewSet.as_view({"get": "reviews"})
    req = rf.get(f"/api/properties/public/{prop.id}/reviews/")
    resp = reviews_view(req, pk=prop.id)
    assert resp.status_code == 200
    # Should return only prop's reviews sorted by -created_at (r2 then r1)
    got_ids = [item["id"] for item in resp.data]
    assert got_ids == [r2.id, r1.id]