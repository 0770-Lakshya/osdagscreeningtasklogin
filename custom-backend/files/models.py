from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone


def user_file_upload_path(instance, filename):
    safe_name = f"{uuid4().hex}_{filename}"
    return f"user_files/user_{instance.owner_id}/{safe_name}"


class UserFile(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="files",
    )
    name = models.CharField(max_length=255)
    des = models.TextField(blank=True)
    content = models.FileField(upload_to=user_file_upload_path)
    size = models.PositiveBigIntegerField(default=0)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-uploaded_at",)

    def __str__(self):
        return f"{self.name} (owner={self.owner.email})"
