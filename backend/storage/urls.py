from django.urls import path

from .views import (
    ChunkedUploadChunkView,
    ChunkedUploadCompleteView,
    ChunkedUploadInitView,
    DashboardStatsView,
    DirectoryContentsView,
    FileDeleteView,
    FileDownloadView,
    FileRenameView,
    FileUploadView,
    FolderDetailView,
    FolderListCreateView,
    PresignedUploadConfirmView,
    PresignedUploadInitView,
    ShareLinkDetailView,
    ShareLinkListCreateView,
)

urlpatterns = [
    path("dashboard/", DashboardStatsView.as_view(), name="storage-dashboard"),
    path("items/", DirectoryContentsView.as_view(), name="storage-items"),
    path("folders/", FolderListCreateView.as_view(), name="folder-list-create"),
    path("folders/<uuid:folder_id>/", FolderDetailView.as_view(), name="folder-detail"),
    path("files/upload/", FileUploadView.as_view(), name="file-upload"),
    path("files/upload/presign/", PresignedUploadInitView.as_view(), name="file-upload-presign"),
    path("files/upload/confirm/", PresignedUploadConfirmView.as_view(), name="file-upload-confirm"),
    path("files/upload/init/", ChunkedUploadInitView.as_view(), name="file-chunk-init"),
    path("files/upload/chunk/", ChunkedUploadChunkView.as_view(), name="file-chunk-part"),
    path("files/upload/complete/", ChunkedUploadCompleteView.as_view(), name="file-chunk-complete"),
    path("files/<uuid:file_id>/download/", FileDownloadView.as_view(), name="file-download"),
    path("files/<uuid:file_id>/rename/", FileRenameView.as_view(), name="file-rename"),
    path("files/<uuid:file_id>/", FileDeleteView.as_view(), name="file-delete"),
    path("shares/", ShareLinkListCreateView.as_view(), name="share-list-create"),
    path("shares/<uuid:share_id>/", ShareLinkDetailView.as_view(), name="share-detail"),
]
