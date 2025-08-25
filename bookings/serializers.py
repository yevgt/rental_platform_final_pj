from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from .models import Booking, Message
from properties.models import Property

class BookingSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    property_owner_id = serializers.IntegerField(source="property.owner.id", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "property", "user_id", "status",
            "start_date", "end_date", "monthly_rent", "total_amount",
             "cancel_until", "created_at", "property_owner_id",
        ]
        read_only_fields = [
            "id", "user_id", "user", "property_owner_id", "status",
            "monthly_rent", "total_amount", "cancel_until",
            "created_at", "confirmed_at",
        ]

    def validate(self, attrs):
        prop = attrs.get("property")
        start = attrs.get("start_date")
        end = attrs.get("end_date")

        if not start or not end:
            raise serializers.ValidationError("start and end must be specified")
        if start >= end:
            raise serializers.ValidationError("start_date should be earlier end_date.")
        today = timezone.now().date()
        if start < today:
            raise serializers.ValidationError("You cannot book past dates..")
        if prop.status != Property.Status.ACTIVE:
            raise serializers.ValidationError("You cannot book an inactive listing.")

        overlap = Booking.objects.filter(
            # property=prop, status=Booking.Status.CONFIRMED
            property=prop,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.PENDING]
        ).filter(
            Q(start_date__lt=end) & Q(end_date__gt=start)
        ).exists()
        if overlap:
            raise serializers.ValidationError("There are already confirmed reservations for these dates.")
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        prop = validated_data["property"]

        if user == prop.owner:
            raise serializers.ValidationError("The owner cannot book his own property.")

        # берем цену; если у вас только price
        price_monthly = getattr(prop, "price_monthly", None)
        if price_monthly is None:
            price_monthly = getattr(prop, "price")

        validated_data["monthly_rent"] = price_monthly
        start_date = validated_data["start_date"]
        end_date = validated_data["end_date"]
        days = (end_date - start_date).days
        months = (Decimal(days) / Decimal("30.44"))
        total_amount = (price_monthly * months).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        validated_data["total_amount"] = total_amount
        validated_data["cancel_until"] = start_date

        return Booking.objects.create(
            user=user,
            status=Booking.Status.PENDING,
            **validated_data
        )

class MessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(source="sender.id", read_only=True)
    receiver_id = serializers.IntegerField(source="receiver.id", read_only=True)

    class Meta:
        model = Message
        fields = ["id", "booking", "sender_id", "receiver_id", "text", "created_at"]
        read_only_fields = ["id", "booking", "sender_id", "receiver_id", "created_at"]