from django.http import HttpResponse
from django.urls import reverse


def bookings_root(request):
    """
    Корневая страница для /api/bookings/
    Показывает ключевые эндпоинты бронирований.
    """
    lines = []
    try:
        list_url = reverse("booking-list")
        create_url = reverse("booking-create")

        lines.append(f'<li>Список бронирований (GET)</a> (renter: свои, landlord: по своим объявлениям)</li>')
        lines.append(f'<li><a href="{create_url}">Создание бронирования (GET/POST): /api/bookings/create/</a></li>')
        lines.append('<li>Деталь бронирования (GET): /api/bookings/&lt;id&gt;/</li>')
        lines.append('<li>Отмена (renter, POST): /api/bookings/&lt;id&gt;/cancel/</li>')
        lines.append('<li>Подтвердить (landlord, POST): /api/bookings/&lt;id&gt;/confirm/</li>')
        lines.append('<li>Отклонить (landlord, POST): /api/bookings/&lt;id&gt;/reject/</li>')
        lines.append('<li>Сообщения (GET/POST): /api/bookings/&lt;id&gt;/messages/</li>')
        lines.append('<li>Доступные объекты для брони (GET): /api/bookings/available_properties/</li>')
    except Exception:
        pass

    html = f"""
    <h1>Bookings API root</h1>
    <ul>
        {''.join(lines)}
    </ul>
    <p>Фильтры (query params списка бронирований): status, property_id, renter_id, start_date_from, start_date_to, end_date_from, end_date_to.</p>
    <p>Поиск: ?search=строка (по property.title/location). Ordering: ?ordering=-created_at или start_date и т.д.</p>
    """
    return HttpResponse(html)