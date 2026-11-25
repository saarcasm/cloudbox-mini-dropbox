from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from storage.views import PublicShareDetailView, PublicShareDownloadView


def health_check(_request):
    return JsonResponse({"status": "ok", "service": "CloudBox API"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health-check"),
    path("api/auth/", include("accounts.urls")),
    path("api/storage/", include("storage.urls")),
    path("api/share/<str:token>/", PublicShareDetailView.as_view(), name="public-share-detail"),
    path("api/share/<str:token>/download/", PublicShareDownloadView.as_view(), name="public-share-download"),
]
