from django.http import HttpResponse
from django.urls import reverse


def bookings_root(request):
    """
    Root page for /api/bookings/
    Shows key bookings endpoints.
    """
    lines = []
    try:
        list_url = reverse("booking-list")
        create_url = reverse("booking-create")

        lines.append(f'<li>List of bookings (GET)</a> (renter: own, landlord: by own ads)</li>')
        lines.append(f'<li><a href="{create_url}">Create a booking (GET/POST): /api/bookings/create/</a></li>')
        lines.append('<li>Booking Details (GET): /api/bookings/&lt;id&gt;/</li>')
        lines.append('<li>Cancel (renter, POST): /api/bookings/&lt;id&gt;/cancel/</li>')
        lines.append('<li>Confirm (landlord, POST): /api/bookings/&lt;id&gt;/confirm/</li>')
        lines.append('<li>Reject (landlord, POST): /api/bookings/&lt;id&gt;/reject/</li>')
        lines.append('<li>Messages (GET/POST): /api/bookings/&lt;id&gt;/messages/</li>')
        lines.append('<li>Available objects for booking (GET): /api/bookings/available_properties/</li>')
    except Exception:
        pass

    html = f"""
    <h1>Bookings API root</h1>
    <ul>
        {''.join(lines)}
    </ul>
    <p>Filters (query params of the booking list): status, property_id, renter_id, start_date_from, start_date_to, end_date_from, end_date_to.</p>
    <p>Поиск: ?search=строка (по property.title/location). Ordering: ?ordering=-created_at or start_date etc.</p>
    """
    return HttpResponse(html)