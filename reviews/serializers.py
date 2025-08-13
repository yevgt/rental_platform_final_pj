from datetime import date
from rest_framework import serializers
from django.utils import timezone
from .models import Review
from bookings.models import Booking

MAX_COMMENT_LEN = 1000

class ReviewSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "property", "user_id", "rating", "comment", "created_at"]
        read_only_fields = ["id", "created_at", "user_id"]

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be from 1 to 5.")
        return value

    def validate_comment(self, value: str):
        value = (value or "").strip()
        if len(value) > MAX_COMMENT_LEN:
            raise serializers.ValidationError(f"The comment is too long (maximum {MAX_COMMENT_LEN} symbols).")
        # Simple "text" check - filter out controls except standard hyphens
        for ch in value:
            if ord(ch) < 32 and ch not in ("\n", "\r", "\t"):
                raise serializers.ValidationError("The comment contains invalid control characters..")
        return value

    def validate(self, attrs):
        # request = self.context["request"]
        # user = request.user
        user = self.context["request"].user
        prop = attrs.get("property")
        if not prop:
            return attrs
        today = timezone.now().date()
        # There must be a confirmed booking that has already been completed.
        has_finished_booking = Booking.objects.filter(
            property=prop,
            user=user,
            status=Booking.Status.CONFIRMED,
            # end_date__lt=date.today()
            end_date__lt=today
        ).exists()
        if not has_finished_booking:
            raise serializers.ValidationError("You can only leave a review after a completed, confirmed booking..")
        return attrs

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Prevent changing the property object when updating
        if "property" in validated_data:
            validated_data.pop("property")
        return super().update(instance, validated_data)