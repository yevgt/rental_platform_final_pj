from rest_framework.views import APIView
from rest_framework import response, permissions

class PropertiesDocsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        html = """
        <h1>Properties API docs</h1>
        <ul>
          <li><b>[PRIVATE]</b> Мои объявления (GET, HTML форма создания доступна если landlord): <code>/api/properties/</code></li>
          <li>Создание (POST): <code>/api/properties/</code></li>
          <li>Деталь (GET/PUT/PATCH/DELETE): <code>/api/properties/&lt;id&gt;/</code></li>
          <li>Переключить статус (POST): <code>/api/properties/&lt;id&gt;/toggle_status/</code></li>
          <li>Загрузить изображения (POST multipart): <code>/api/properties/&lt;id&gt;/upload-images/</code></li>
          <li>Удалить изображение (POST): <code>/api/properties/&lt;id&gt;/delete-image/</code></li>
          <li>Переупорядочить изображения (POST): <code>/api/properties/&lt;id&gt;/reorder-images/</code></li>
          <li>Обновить подпись изображения (POST): <code>/api/properties/&lt;id&gt;/update-image-caption/</code></li>
          <li>Установить / очистить главную картинку (POST): <code>/api/properties/&lt;id&gt;/set-main-image/</code></li>
          <li><b>[PUBLIC]</b> Список активных: <code>/api/properties/public/</code></li>
          <li>Публичная деталь: <code>/api/properties/public/&lt;id&gt;/</code></li>
        </ul>
        <p>Фильтры (public): price_min, price_max, rooms_min, rooms_max, location, property_type, search, ordering.</p>
        <p>Примеры сортировки: ?ordering=-created_at, ?ordering=price</p>
        """
        return response.Response(html, content_type="text/html")