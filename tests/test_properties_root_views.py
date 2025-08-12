import pytest
from django.test import RequestFactory

import properties.root_views as rv


@pytest.fixture
def rf():
    return RequestFactory()


def test_properties_root_with_urls_success(monkeypatch, rf):
    # Map URL names to fake paths
    def fake_reverse(name):
        mapping = {
            "property-list": "/api/properties/",
            "property-create": "/api/properties/create/",
            "public-property-list": "/api/properties/public/",
        }
        return mapping[name]

    # Patch reverse inside the module under test
    monkeypatch.setattr(rv, "reverse", fake_reverse, raising=True)

    request = rf.get("/api/properties/")
    resp = rv.properties_root(request)

    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    # Private section
    assert "Список моих объявлений" in html  # label presence
    assert '<a href="/api/properties/create/">Создание объявления (GET/POST): /api/properties/create/</a>' in html
    assert "Создание объявления (POST) : /api/properties/" in html
    assert "Деталь объявления (GET/PUT/PATCH/DELETE): /api/properties/&lt;id&gt;/" in html
    assert "Переключить статус (POST): /api/properties/&lt;id&gt;/toggle_status/" in html
    assert "Загрузить изображения (POST multipart): /api/properties/&lt;id&gt;/upload-images/" in html
    assert "Удалить изображение (POST): /api/properties/&lt;id&gt;/delete-image/" in html
    assert "Переупорядочить изображения (POST): /api/properties/&lt;id&gt;/reorder-images/" in html
    assert "Обновить подпись изображения (POST): /api/properties/&lt;id&gt;/update-image-caption/" in html
    assert "Установить / очистить главную картинку (POST): /api/properties/&lt;id&gt;/set-main-image/" in html

    # Public section
    assert '<a href="/api/properties/public/">[PUBLIC] Публичный список активных объявлений (GET)</a>' in html
    assert "Публичная деталь (GET): /api/properties/public/&lt;id&gt;/" in html

    # Footer hints about filters and ordering
    assert "Фильтры (query params)" in html
    assert "Ordering примеры" in html


def test_properties_root_when_reverse_raises(monkeypatch, rf):
    # Force reverse to fail to cover except branches
    def raising_reverse(*args, **kwargs):
        raise Exception("no urls")

    monkeypatch.setattr(rv, "reverse", raising_reverse, raising=True)

    request = rf.get("/api/properties/")
    resp = rv.properties_root(request)

    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    # No links should be rendered from try blocks
    assert "[PRIVATE]" not in html
    assert "[PUBLIC]" not in html
    assert "Создание объявления" not in html

    # Still renders header and footer hints
    assert "<h1>Properties API root</h1>" in html
    assert "Фильтры (query params)" in html
    assert "Ordering примеры" in html