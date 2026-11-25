from rest_framework import serializers

from .models import Folder, ShareLink, StoredFile


class FolderSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()
    active_share_token = serializers.SerializerMethodField()

    class Meta:
        model = Folder
        fields = [
            "id",
            "name",
            "parent",
            "item_count",
            "active_share_token",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_item_count(self, obj):
        return obj.subfolders.count() + obj.files.count()

    def get_active_share_token(self, obj):
        link = obj.share_links.filter(is_active=True).first()
        if link and link.is_accessible:
            return link.token
        return None


class StoredFileSerializer(serializers.ModelSerializer):
    folder_name = serializers.CharField(source="folder.name", read_only=True, default=None)
    active_share_token = serializers.SerializerMethodField()

    class Meta:
        model = StoredFile
        fields = [
            "id",
            "name",
            "folder",
            "folder_name",
            "size_bytes",
            "content_type",
            "checksum_sha256",
            "encrypted_at_rest",
            "active_share_token",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "size_bytes",
            "content_type",
            "checksum_sha256",
            "encrypted_at_rest",
            "created_at",
            "updated_at",
        ]

    def get_active_share_token(self, obj):
        link = obj.share_links.filter(is_active=True).first()
        if link and link.is_accessible:
            return link.token
        return None


class ShareLinkSerializer(serializers.ModelSerializer):
    target_type = serializers.SerializerMethodField()
    target_name = serializers.SerializerMethodField()
    target_size_bytes = serializers.SerializerMethodField()
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = ShareLink
        fields = [
            "id",
            "token",
            "file",
            "folder",
            "target_type",
            "target_name",
            "target_size_bytes",
            "is_active",
            "is_expired",
            "expires_at",
            "download_count",
            "created_at",
        ]
        read_only_fields = ["id", "token", "download_count", "created_at"]

    def get_target_type(self, obj):
        return "file" if obj.file_id else "folder"

    def get_target_name(self, obj):
        if obj.file:
            return obj.file.name
        if obj.folder:
            return obj.folder.name
        return "Unknown"

    def get_target_size_bytes(self, obj):
        if obj.file:
            return obj.file.size_bytes
        return None
