from datetime import date
from rest_framework import serializers
from django.utils import timezone
from .models import Review
from bookings.models import Booking

class ReviewSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "property", "user_id", "rating", "comment", "created_at"]
        read_only_fields = ["id", "created_at", "user_id"]

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Рейтинг должен быть от 1 до 5.")
        return value

    def validate(self, attrs):
        # request = self.context["request"]
        # user = request.user
        user = self.context["request"].user
        prop = attrs.get("property")
        today = timezone.now().date()
        # Должно быть подтвержденное бронирование, которое уже завершено
        has_finished_booking = Booking.objects.filter(
            property=prop,
            user=user,
            status=Booking.Status.CONFIRMED,
            # end_date__lt=date.today()
            end_date__lt=today
        ).exists()
        if not has_finished_booking:
            raise serializers.ValidationError("Оставлять отзыв можно только после завершенного подтвержденного бронирования.")
        return attrs

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)