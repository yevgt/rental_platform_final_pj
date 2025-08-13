from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

User = get_user_model()

def _validate_date_of_birth(dob):
    """General function for checking date of birth."""
    if dob is None:
        raise serializers.ValidationError("Date of birth is required.")
    today = timezone.now().date()
    if dob > today:
        raise serializers.ValidationError("Date of birth cannot be in the future.")
    # Age calculation
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age < 18:
        raise serializers.ValidationError("Registration is allowed only for users 18+.")
    return dob

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "first_name", "last_name",
            "email", "role", "phone_number",
            "profile_picture", "date_of_birth",
        ]
        read_only_fields = ["id"]

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    password_confirm = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})
    date_of_birth = serializers.DateField(required=True)

    class Meta:
        model = User
        fields = [
            "id", "first_name", "last_name",
            "email", "password", "password_confirm",
            "role", "date_of_birth", "phone_number", "profile_picture",
        ]
        read_only_fields = ["id"]


    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_date_of_birth(self, value):
        return _validate_date_of_birth(value)

    def validate(self, attrs):
        pw = attrs.get("password")
        pw2 = attrs.pop("password_confirm", None)
        if pw != pw2:
            raise serializers.ValidationError({"password_confirm": "The passwords do not match."})
        validate_password(pw)
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.username = user.email
        user.set_password(password)
        user.save()
        return user

class ProfileUpdateSerializer(serializers.ModelSerializer):
    """
    User profile update.
    """

    date_of_birth = serializers.DateField(required=False)

    class Meta:
        model = User
        fields = [
            "first_name", "last_name",
            "phone_number", "profile_picture",
            "date_of_birth", "email", "role"
        ]

    def validate_email(self, value):
        user = self.instance
        if user and user.email.lower() == value.lower():
            return value
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email is already taken.")
        return value

    def validate_role(self, value):
        if value not in [c[0] for c in User.Roles.choices]:
            raise serializers.ValidationError("Incorrect role.")
        return value

    def validate_date_of_birth(self, value):
        return _validate_date_of_birth(value)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        user = self.context["request"].user
        old = attrs.get("old_password")
        if not user.check_password(old):
            raise serializers.ValidationError({"old_password": "Incorrect current password."})
        new = attrs.get("new_password")
        new2 = attrs.pop("new_password_confirm", None)
        if new != new2:
            raise serializers.ValidationError({"new_password_confirm": "Confirmation does not match."})
        validate_password(new, user=user)
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        new = self.validated_data["new_password"]
        user.set_password(new)
        user.save(update_fields=["password"])
        return user