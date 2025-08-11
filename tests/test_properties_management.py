import pytest
from rest_framework.test import APIClient
from properties.models import Property
from django.utils import timezone

@pytest.mark.django_db
class TestPropertyManagement:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def landlord(self, django_user_model):
        return django_user_model.objects.create_user(
            email="landlord@example.com",
            password="Pass12345",
            role="landlord",
            first_name="L",
            last_name="Owner",
            date_of_birth="1990-01-01",
        )

    @pytest.fixture
    def other_landlord(self, django_user_model):
        return django_user_model.objects.create_user(
            email="landlord2@example.com",
            password="Pass12345",
            role="landlord",
            first_name="L2",
            last_name="Owner2",
            date_of_birth="1990-01-01",
        )

    @pytest.fixture
    def renter(self, django_user_model):
        return django_user_model.objects.create_user(
            email="renter@example.com",
            password="Pass12345",
            role="renter",
            first_name="R",
            last_name="User",
            date_of_birth="1995-01-01",
        )

    def auth(self, client, user):
        resp = client.post("/api/token/", {"email": user.email, "password": "Pass12345"}, format="json")
        assert resp.status_code == 200
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")

    def test_landlord_can_create_property(self, client, landlord):
        self.auth(client, landlord)
        data = {
            "title": "Уютная квартира",
            "description": "Описание",
            "location": "Berlin",
            "price": "1200.00",
            "number_of_rooms": 2,
            "property_type": "apartment",
        }
        resp = client.post("/api/properties/", data, format="json")
        assert resp.status_code in (201, 200), resp.data
        prop = Property.objects.get(title="Уютная квартира")
        assert prop.owner == landlord

    def test_renter_cannot_create_property(self, client, renter):
        self.auth(client, renter)
        data = {
            "title": "Недопустимо",
            "description": "test",
            "location": "Hamburg",
            "price": "999.00",
            "number_of_rooms": 1,
            "property_type": "apartment",
        }
        resp = client.post("/api/properties/", data, format="json")
        assert resp.status_code == 403

    def test_landlord_can_update_own_property_but_not_others(self, client, landlord, other_landlord):
        # Создаём проперти первого владельца
        p1 = Property.objects.create(
            title="P1",
            description="D1",
            location="Berlin",
            price="1500.00",
            number_of_rooms=3,
            property_type="apartment",
            owner=landlord,
            status=Property.Status.ACTIVE,
        )
        p2 = Property.objects.create(
            title="P2",
            description="D2",
            location="Munich",
            price="2000.00",
            number_of_rooms=4,
            property_type="house",
            owner=other_landlord,
            status=Property.Status.ACTIVE,
        )
        self.auth(client, landlord)

        # Обновляет своё
        resp = client.patch(f"/api/properties/{p1.id}/", {"title": "P1-new"}, format="json")
        assert resp.status_code == 200
        p1.refresh_from_db()
        assert p1.title == "P1-new"

        # Пытается обновить чужое
        resp2 = client.patch(f"/api/properties/{p2.id}/", {"title": "HACK"}, format="json")
        assert resp2.status_code in (403, 404)

    def test_public_view_list_and_retrieve(self, client, landlord):
        Property.objects.create(
            title="Public A",
            description="Desc A",
            location="Berlin",
            price="1100.00",
            number_of_rooms=2,
            property_type="apartment",
            owner=landlord,
            status=Property.Status.ACTIVE,
        )
        resp = client.get("/api/properties/public/")
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        prop_id = resp.data["results"][0]["id"]
        r2 = client.get(f"/api/properties/public/{prop_id}/")
        assert r2.status_code == 200