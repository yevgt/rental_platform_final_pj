from rest_framework import serializers
from .models import Property, Listing

class ListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = ["id", "is_active", "created_at", "updated_at"]
        read_only_fields = fields

class PropertySerializer(serializers.ModelSerializer):
    owner_id = serializers.IntegerField(source="owner.id", read_only=True)
    listing = ListingSerializer(read_only=True)

    class Meta:
        model = Property
        fields = [
            "id", "title", "description", "location", "price",
            "number_of_rooms", "property_type", "owner_id",
            "status", "views_count", "created_at", "updated_at",
            "listing",
        ]
        read_only_fields = ["id", "owner_id", "views_count", "created_at", "updated_at", "listing"]

    # Базовые проверки
    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Цена должна быть > 0.")
        return value

    def validate_number_of_rooms(self, value):
        if value <= 0:
            raise serializers.ValidationError("Количество комнат должно быть > 0.")
        return value


    def create(self, validated_data):
        user = self.context["request"].user
        prop = Property.objects.create(owner=user, **validated_data)
        Listing.objects.create(property=prop, is_active=(prop.status == Property.Status.ACTIVE))
        return prop

    def update(self, instance, validated_data):
        prop = super().update(instance, validated_data)
        # синхронизируем активность листинга с статусом property
        if hasattr(prop, "listing"):
            prop.listing.is_active = (prop.status == prop.Status.ACTIVE)
            prop.listing.save(update_fields=["is_active"])
        return prop