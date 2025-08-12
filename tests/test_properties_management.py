import json
import pytest
from rest_framework.test import APIClient
from properties.models import Property


def _json(resp):
    try:
        return resp.json()
    except Exception:
        try:
            raw = getattr(resp, "content", b"")
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="ignore")
            return json.loads(raw)
        except Exception:
            return None


def _list_items(resp):
    data = _json(resp)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "data", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def _extract_created_property_from_response(resp, owner):
    """
    Try to get created Property instance from response payload (id or fields).
    Fallback to last created property by title+owner if payload doesn't contain id.
    """
    payload = _json(resp)
    if isinstance(payload, dict):
        created_id = (
            payload.get("id")
            or (payload.get("data") or {}).get("id")
            or (payload.get("result") or {}).get("id")
        )
        if created_id:
            return Property.objects.filter(id=created_id).first()

        # Some views echo the object fields directly
        title = payload.get("title") or (payload.get("data") or {}).get("title")
        if title:
            obj = Property.objects.filter(title=title, owner=owner).order_by("-id").first()
            if obj:
                return obj
    return None


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

    def auth(self, client: APIClient, user):
        """
        Authenticate the APIClient as the given user using multiple strategies:
        - JWT token (Bearer, common field names).
        - Session login (username/email).
        - force_login/force_authenticate as fallbacks.
        """
        token = None
        try:
            resp = client.post("/api/token/", {"email": user.email, "password": "Pass12345"}, format="json")
            if getattr(resp, "status_code", None) == 200:
                data = getattr(resp, "data", {}) or _json(resp) or {}
                for key in ("access", "token", "access_token", "key"):
                    if data and isinstance(data, dict) and data.get(key):
                        token = data[key]
                        break
        except Exception:
            pass

        if token:
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # Try session login with both parameter names
        try:
            client.logout()
        except Exception:
            pass
        # username/email depending on USERNAME_FIELD
        logged_in = False
        for creds in (
            {"username": user.email, "password": "Pass12345"},
            {"email": user.email, "password": "Pass12345"},
        ):
            try:
                if client.login(**creds):
                    logged_in = True
                    break
            except Exception:
                # Some APIClient versions don't support login kwargs other than username/password
                try:
                    if client.login(username=user.email, password="Pass12345"):
                        logged_in = True
                        break
                except Exception:
                    pass

        # Ensure authenticated on DRF stack regardless of auth backends
        try:
            client.force_login(user)
        except Exception:
            pass
        try:
            client.force_authenticate(user=user)
        except Exception:
            pass

    def _post_create_candidates(self, client: APIClient, data: dict, owner) -> tuple[Property | None, list]:
        """
        Try multiple create endpoints. Return (created_property_or_none, debug_info).
        debug_info is list of tuples: (url, status_code, body_preview)
        """
        candidates = [
            "/api/properties/",
            "/api/landlord/properties/",
            "/api/properties/create/",
        ]
        debug = []
        for url in candidates:
            resp = client.post(url, data, format="json", follow=True)
            body = _json(resp)
            # Capture small preview for debugging
            preview = body if isinstance(body, (dict, list)) else (getattr(resp, "content", b"")[:200])
            debug.append((url, resp.status_code, preview))
            if resp.status_code in (201, 200):
                created = _extract_created_property_from_response(resp, owner)
                if created is None:
                    # Fallback: search by title+owner if present
                    title = data.get("title")
                    if title:
                        created = Property.objects.filter(title=title, owner=owner).order_by("-id").first()
                if created:
                    return created, debug
        return None, debug

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
        created, debug = self._post_create_candidates(client, data, landlord)
        assert created is not None, f"Property not created. Tried: {debug}"
        assert created.owner == landlord

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
        created, debug = self._post_create_candidates(client, data, renter)
        # Either API explicitly forbids (403/401), or simply doesn't create the record.
        assert created is None, f"Renter should not create property, but created: {created}. Debug: {debug}"
        assert not Property.objects.filter(title="Недопустимо", owner=renter).exists()

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
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code}, body={_json(resp)}"
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
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code}"

        # Support both paginated and plain list responses
        items = _list_items(resp)
        data = _json(resp)
        if isinstance(data, dict) and "count" in data:
            assert data["count"] >= 1, f"Wrong count: {data}"
        else:
            assert len(items) >= 1, f"Wrong items length: {items}"

        prop_id = items[0]["id"]
        r2 = client.get(f"/api/properties/public/{prop_id}/")
        if r2.status_code == 404:
            # Some implementations don't have /public/<id>/, fall back to generic detail
            r2 = client.get(f"/api/properties/{prop_id}/")
        assert r2.status_code == 200, f"Unexpected detail status: {r2.status_code}, body={_json(r2)}"