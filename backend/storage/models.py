import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_share_token() -> str:
    return secrets.token_urlsafe(18)


class Folder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="folders"
    )
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="subfolders"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "parent", "name"], name="unique_folder_name_per_parent"
            )
        ]

    def __str__(self):
        return self.name


class StoredFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stored_files"
    )
    folder = models.ForeignKey(
        Folder, null=True, blank=True, on_delete=models.CASCADE, related_name="files"
    )
    name = models.CharField(max_length=255)
    object_key = models.CharField(max_length=512, unique=True)
    size_bytes = models.BigIntegerField(default=0)
    content_type = models.CharField(max_length=255, default="application/octet-stream")
    checksum_sha256 = models.CharField(max_length=64, blank=True, default="")
    encrypted_at_rest = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class ChunkedUploadSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="upload_sessions"
    )
    folder = models.ForeignKey(
        Folder, null=True, blank=True, on_delete=models.SET_NULL, related_name="upload_sessions"
    )
    filename = models.CharField(max_length=255)
    total_size = models.BigIntegerField()
    total_chunks = models.PositiveIntegerField()
    content_type = models.CharField(max_length=255, default="application/octet-stream")
    created_at = models.DateTimeField(auto_now_add=True)


class ShareLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=64, unique=True, default=generate_share_token)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="share_links"
    )
    file = models.ForeignKey(
        StoredFile, null=True, blank=True, on_delete=models.CASCADE, related_name="share_links"
    )
    folder = models.ForeignKey(
        Folder, null=True, blank=True, on_delete=models.CASCADE, related_name="share_links"
    )
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and timezone.now() > self.expires_at)

    @property
    def is_accessible(self) -> bool:
        return self.is_active and not self.is_expired
