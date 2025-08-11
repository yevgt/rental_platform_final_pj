from django.http import HttpResponse
from django.urls import reverse


def properties_root(request):
    """
    Корневая страница для /api/properties/
    Показывает ключевые эндпоинты (приватные для landlord и публичный каталог).
    """
    lines = []

    # Базовые (private) viewset routes (для landlord)
    try:
        private_list = reverse("property-list")
        create_url = reverse("property-create")  # добавили ссылку на алиас создания

        lines.append(f'<li> [PRIVATE] Список моих объявлений </a></li>')
        # Новая кликабельная ссылка на создание
        lines.append(f'<li><a href="{create_url}">Создание объявления (GET/POST): /api/properties/create/</a></li>')

        # lines.append(f'<li><a href="{private_list}">[PRIVATE] Список моих объявлений (GET)</a></li>')
        lines.append(f'<li>Создание объявления (POST) : {private_list}</li>')
        lines.append('<li>Деталь объявления (GET/PUT/PATCH/DELETE): /api/properties/&lt;id&gt;/</li>')
        lines.append('<li>Переключить статус (POST): /api/properties/&lt;id&gt;/toggle_status/</li>')
        lines.append('<li>Загрузить изображения (POST multipart): /api/properties/&lt;id&gt;/upload-images/</li>')
        lines.append('<li>Удалить изображение (POST): /api/properties/&lt;id&gt;/delete-image/</li>')
        lines.append('<li>Переупорядочить изображения (POST): /api/properties/&lt;id&gt;/reorder-images/</li>')
        lines.append('<li>Обновить подпись изображения (POST): /api/properties/&lt;id&gt;/update-image-caption/</li>')
        lines.append('<li>Установить / очистить главную картинку (POST): /api/properties/&lt;id&gt;/set-main-image/</li>')
    except Exception:
        pass

    # Публичный каталог
    try:
        public_list = reverse("public-property-list")
        lines.append(f'<li><a href="{public_list}">[PUBLIC] Публичный список активных объявлений (GET)</a></li>')
        lines.append('<li>Публичная деталь (GET): /api/properties/public/&lt;id&gt;/</li>')
    except Exception:
        pass

    html = f"""
    <h1>Properties API root</h1>
    <ul>
        {''.join(lines)}
    </ul>
    <p>Фильтры (query params): price_min, price_max, rooms_min, rooms_max, location, property_type, search, ordering.</p>
    <p>Ordering примеры: ?ordering=-created_at, ?ordering=price</p>
    """
    return HttpResponse(html)