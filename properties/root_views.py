from django.http import HttpResponse
from django.urls import reverse


def properties_root(request):
    """
    Root page for /api/properties/
    Shows key endpoints (private for landlord and public directory).
    """
    lines = []

    # Basic (private) viewset routes (for landlord)
    try:
        private_list = reverse("property-list")
        create_url = reverse("property-create")

        lines.append(f'<li> [PRIVATE] List of my ads </a></li>')
        # New clickable link to create
        lines.append(f'<li><a href="{create_url}">Creating an ad (GET/POST): /api/properties/create/</a></li>')

        # lines.append(f'<li><a href="{private_list}">[PRIVATE] Список моих объявлений (GET)</a></li>')
        # lines.append(f'<li>Создание объявления (POST) : {private_list}</li>')
        lines.append('<li>Ad Details (GET/PUT/PATCH/DELETE): /api/properties/&lt;id&gt;/</li>')
        lines.append('<li>Toggle status (POST): /api/properties/&lt;id&gt;/toggle_status/</li>')
        lines.append('<li>Upload images (POST multipart): /api/properties/&lt;id&gt;/upload-images/</li>')
        lines.append('<li>Delete image (POST): /api/properties/&lt;id&gt;/delete-image/</li>')
        lines.append('<li>Reorder images (POST): /api/properties/&lt;id&gt;/reorder-images/</li>')
        lines.append('<li>Update image caption (POST): /api/properties/&lt;id&gt;/update-image-caption/</li>')
        lines.append('<li>Set/clear main image (POST): /api/properties/&lt;id&gt;/set-main-image/</li>')
    except Exception:
        pass

    # Public directory
    try:
        public_list = reverse("public-property-list")
        lines.append(f'<li><a href="{public_list}">[PUBLIC] Public list of active ads (GET)</a></li>')
        lines.append('<li>Public detail (GET): /api/properties/public/&lt;id&gt;/</li>')
    except Exception:
        pass

    html = f"""
    <h1>Properties API root</h1>
    <ul>
        {''.join(lines)}
    </ul>
    <p>Filters (query params): price_min, price_max, rooms_min, rooms_max, location, property_type, search, ordering.</p>
    <p>Ordering examples: ?ordering=-created_at, ?ordering=price</p>
    """
    return HttpResponse(html)