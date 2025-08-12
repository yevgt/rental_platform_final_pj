import pytest
from django.test import RequestFactory

import bookings.root_views as rv


@pytest.mark.django_db
def test_bookings_root_success_includes_links(monkeypatch):
    factory = RequestFactory()

    def fake_reverse(name, *args, **kwargs):
        if name == "booking-list":
            return "/api/bookings/"
        if name == "booking-create":
            return "/api/bookings/create/"
        return "/unknown/"

    monkeypatch.setattr(rv, "reverse", fake_reverse, raising=True)

    req = factory.get("/api/bookings/")
    resp = rv.bookings_root(req)
    html = resp.content.decode("utf-8")

    assert resp.status_code == 200
    assert "<h1>Bookings API root</h1>" in html

    # Создание бронирования с ссылкой (используется create_url)
    assert '<a href="/api/bookings/create/">' in html

    # Остальные подсказки присутствуют как статический текст
    assert "Список бронирований (GET)" in html
    assert "Деталь бронирования (GET): /api/bookings&lt;id&gt;/" in html or "Деталь бронирования (GET): /api/bookings/&lt;id&gt;/" in html
    assert "Отмена (renter, POST)" in html
    assert "Подтвердить (landlord, POST)" in html
    assert "Отклонить (landlord, POST)" in html
    assert "Сообщения (GET/POST)" in html
    assert "Доступные объекты для брони (GET)" in html

    # Блок с описанием фильтров/поиска
    assert "Фильтры (query params списка бронирований)" in html
    assert "Ordering: ?ordering=" in html


@pytest.mark.django_db
def test_bookings_root_handles_reverse_errors(monkeypatch):
    factory = RequestFactory()

    def raise_reverse(*args, **kwargs):
        raise Exception("no urls")

    monkeypatch.setattr(rv, "reverse", raise_reverse, raising=True)

    req = factory.get("/api/bookings/")
    resp = rv.bookings_root(req)
    html = resp.content.decode("utf-8")

    assert resp.status_code == 200
    assert "<h1>Bookings API root</h1>" in html

    # При ошибке reverse список ссылок пуст, но страница рендерится
    assert "<ul>" in html and "</ul>" in html
    assert "<li>" not in html or "Создание бронирования" not in html
    # Блоки описания всё равно присутствуют
    assert "Фильтры (query params списка бронирований)" in html