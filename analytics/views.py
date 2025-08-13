from django.db.models import Count
from rest_framework import views, permissions, decorators, response
from rest_framework.response import Response
from properties.models import Property
from .models import SearchHistory, ViewHistory
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.reverse import reverse

class TopPropertiesView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        by = request.query_params.get("by", "views")
        limit = int(request.query_params.get("limit", 10))
        if by == "reviews":
            qs = Property.objects.annotate(reviews_count=Count("reviews")).order_by("-reviews_count")[:limit]
            data = [{"id": p.id, "title": p.title, "reviews_count": p.reviews_count} for p in qs]
        else:
            qs = Property.objects.order_by("-views_count")[:limit]
            data = [{"id": p.id, "title": p.title, "views_count": p.views_count} for p in qs]
        return Response(data)

class PopularSearchesView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        limit = int(request.query_params.get("limit", 10))
        qs = SearchHistory.objects.values("search_query").annotate(cnt=Count("id")).order_by("-cnt")[:limit]
        data = [{"query": r["search_query"], "count": r["cnt"]} for r in qs]
        return Response(data)

@api_view(["GET"])
@permission_classes([AllowAny])
def analytics_root(request, format=None):
    return Response({
        "top_properties": reverse("top-properties", request=request, format=format),
        "popular_searches": reverse("popular-searches", request=request, format=format),
    })

