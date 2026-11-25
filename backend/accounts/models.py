from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    storage_quota_bytes = models.BigIntegerField(default=settings.DEFAULT_STORAGE_QUOTA_BYTES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profile({self.user.username})"

    @property
    def used_storage_bytes(self) -> int:
        from storage.models import StoredFile

        agg = StoredFile.objects.filter(owner=self.user).aggregate(total=models.Sum("size_bytes"))
        return agg["total"] or 0

    @property
    def available_storage_bytes(self) -> int:
        return max(0, self.storage_quota_bytes - self.used_storage_bytes)
