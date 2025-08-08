from datetime import date
from django.db.models import Q
from rest_framework import serializers
from .models import Booking, Message
from properties.models import Property

class BookingSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    property_owner_id = serializers.IntegerField(source="property.owner.id", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "property", "user_id", "start_date", "end_date",
            "status", "cancel_until", "created_at", "property_owner_id",
        ]
        read_only_fields = ["status", "created_at", "user_id", "property_owner_id"]

    def validate(self, attrs):
        prop = attrs.get("property")
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start >= end:
            raise serializers.ValidationError("start_date должен быть раньше end_date.")
        if prop.status != Property.Status.ACTIVE:
            raise serializers.ValidationError("Нельзя бронировать неактивное объявление.")
        overlap = Booking.objects.filter(
            property=prop, status=Booking.Status.CONFIRMED
        ).filter(
            Q(start_date__lt=end) & Q(end_date__gt=start)
        ).exists()
        if overlap:
            raise serializers.ValidationError("На эти даты уже есть подтверждённое бронирование.")
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        prop = validated_data["property"]
        if user == prop.owner:
            raise serializers.ValidationError("Владелец не может бронировать собственный объект.")
        return Booking.objects.create(user=user, status=Booking.Status.PENDING, **validated_data)

class MessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(source="sender.id", read_only=True)
    receiver_id = serializers.IntegerField(source="receiver.id", read_only=True)

    class Meta:
        model = Message
        fields = ["id", "booking", "sender_id", "receiver_id", "text", "created_at"]
        read_only_fields = ["id", "booking", "sender_id", "receiver_id", "created_at"]