from rest_framework import serializers
from .models import Property, PropertyImage, Listing
from reviews.models import Review


class PropertyImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = PropertyImage
        fields = ['id', 'url', 'caption', 'order', 'created_at']
        read_only_fields = ['id', 'url', 'created_at']

    def get_url(self, obj):
        request = self.context.get("request")
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        if obj.image:
            return obj.image.url
        return None


class ListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = ["id", "is_active", "created_at", "updated_at"]
        read_only_fields = fields

class PropertySerializer(serializers.ModelSerializer):
    owner_id = serializers.IntegerField(source="owner.id", read_only=True)
    listing = ListingSerializer(read_only=True)
    main_image_url = serializers.SerializerMethodField()
    average_rating = serializers.ReadOnlyField()
    review_count = serializers.ReadOnlyField()
    images = PropertyImageSerializer(many=True, read_only=True)

    # Для загрузки / замены главной картинки при create/update (необязательно)
    main_image = serializers.ImageField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = Property
        fields = [
            "id", "title", "description", "location", "price",
            "number_of_rooms", "property_type", "owner_id",
            "status", "views_count", "created_at", "updated_at",
            "listing", "main_image_url", "main_image",
            "average_rating", "review_count", "images",
        ]

        read_only_fields = [
            "id", "owner_id", "views_count", "created_at", "updated_at",
            "listing", "main_image_url", "average_rating", "review_count",
            "images",
            # если нужно будет запретить прямое изменение статуса:
            # "status"
        ]

    def get_main_image_url(self, obj):
        if obj.main_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.main_image.url)
        return None

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

class PropertyImageUploadSerializer(serializers.Serializer):
    """
    Для action upload_images.
    Принимает:
      - images[]: список файлов
      - captions[]: список подписей (необязательно, по индексу)
    """
    images = serializers.ListField(
        child=serializers.ImageField(),
        allow_empty=False,
        write_only=True
    )
    captions = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        allow_empty=True,
        write_only=True
    )

    def validate(self, attrs):
        images = attrs.get("images", [])
        if len(images) > 10:
            raise serializers.ValidationError("Максимум 10 изображений за раз.")
        return attrs

    def create(self, validated_data):
        # Не используется напрямую, action сам создаёт
        return validated_data

class ReviewSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    booking_id = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["id", "property", "booking_id", "user_id", "rating", "text", "created_at"]
        read_only_fields = fields

    def get_booking_id(self, obj):
        return getattr(obj, "booking_id", None)

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Рейтинг должен быть от 1 до 5.")
        return value