from rest_framework.views import APIView
from rest_framework import response, permissions

class PropertiesDocsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        html = """
        <h1>Properties API docs</h1>
        <ul>
          <li><b>[PRIVATE]</b> My listing (GET, HTML creation form is available if landlord): <code>/api/properties/</code></li>
          <li>Creation (POST): <code>/api/properties/</code></li>
          <li>Detail (GET/PUT/PATCH/DELETE): <code>/api/properties/&lt;id&gt;/</code></li>
          <li>Toggle status (POST): <code>/api/properties/&lt;id&gt;/toggle_status/</code></li>
          <li>Upload images (POST multipart): <code>/api/properties/&lt;id&gt;/upload-images/</code></li>
          <li>Delete image (POST): <code>/api/properties/&lt;id&gt;/delete-image/</code></li>
          <li>Reorder images (POST): <code>/api/properties/&lt;id&gt;/reorder-images/</code></li>
          <li>Update image caption (POST): <code>/api/properties/&lt;id&gt;/update-image-caption/</code></li>
          <li>Set/clear main image (POST): <code>/api/properties/&lt;id&gt;/set-main-image/</code></li>
          <li><b>[PUBLIC]</b> List of active: <code>/api/properties/public/</code></li>
          <li>Public detail: <code>/api/properties/public/&lt;id&gt;/</code></li>
        </ul>
        <p>Filters (public): price_min, price_max, rooms_min, rooms_max, location, property_type, search, ordering.</p>
        <p>Sorting examples: ?ordering=-created_at, ?ordering=price</p>
        """
        return response.Response(html, content_type="text/html")