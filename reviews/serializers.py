from datetime import date
from rest_framework import serializers
from .models import Review
from bookings.models import Booking

class ReviewSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "property", "user_id", "rating", "comment", "created_at"]
        read_only_fields = ["created_at", "user_id"]

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Рейтинг должен быть от 1 до 5.")
        return value

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        prop = attrs.get("property")
        # Должно быть подтвержденное бронирование, которое уже завершено
        has_past_confirmed = Booking.objects.filter(
            property=prop, user=user, status=Booking.Status.CONFIRMED, end_date__lt=date.today()
        ).exists()
        if not has_past_confirmed:
            raise serializers.ValidationError("Оставлять отзыв можно только после завершенного подтвержденного бронирования.")
        return attrs

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)