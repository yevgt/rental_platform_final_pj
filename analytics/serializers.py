from rest_framework import serializers
from .models import ViewHistory, SearchHistory

class ViewHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ViewHistory
        fields = ["id", "user", "property", "viewed_at"]

class SearchHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchHistory
        fields = ["id", "user", "search_query", "searched_at"]