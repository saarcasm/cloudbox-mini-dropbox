from django.contrib import admin

from .models import ChunkedUploadSession, Folder, ShareLink, StoredFile


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "parent", "created_at")


@admin.register(StoredFile)
class StoredFileAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "folder", "size_bytes", "created_at")


@admin.register(ShareLink)
class ShareLinkAdmin(admin.ModelAdmin):
    list_display = ("token", "owner", "file", "folder", "is_active", "download_count", "created_at")


@admin.register(ChunkedUploadSession)
class ChunkedUploadSessionAdmin(admin.ModelAdmin):
    list_display = ("filename", "owner", "total_size", "total_chunks", "created_at")
