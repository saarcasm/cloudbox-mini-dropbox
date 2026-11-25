from django.contrib.auth import get_user_model
from rest_framework import serializers

from storage.models import Folder, StoredFile
from .models import UserProfile

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    quota_bytes = serializers.SerializerMethodField()
    used_bytes = serializers.SerializerMethodField()
    available_bytes = serializers.SerializerMethodField()
    file_count = serializers.SerializerMethodField()
    folder_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "date_joined",
            "quota_bytes",
            "used_bytes",
            "available_bytes",
            "file_count",
            "folder_count",
        ]

    def _get_profile(self, obj):
        profile, _ = UserProfile.objects.get_or_create(user=obj)
        return profile

    def get_quota_bytes(self, obj):
        return self._get_profile(obj).storage_quota_bytes

    def get_used_bytes(self, obj):
        return self._get_profile(obj).used_storage_bytes

    def get_available_bytes(self, obj):
        return self._get_profile(obj).available_storage_bytes

    def get_file_count(self, obj):
        return StoredFile.objects.filter(owner=obj).count()

    def get_folder_count(self, obj):
        return Folder.objects.filter(owner=obj).count()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "first_name", "last_name"]

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        UserProfile.objects.get_or_create(user=user)
        return user
