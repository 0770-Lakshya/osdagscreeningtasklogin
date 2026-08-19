from django.urls import reverse
from rest_framework import serializers

from .models import UserFile


class FileSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = UserFile
        fields = ("id", "name", "des", "size", "uploaded_at", "owner_email", "download_url")
        read_only_fields = ("id", "size", "uploaded_at", "owner_email", "download_url")

    def get_download_url(self, obj):
        return reverse("file-download", kwargs={"pk": obj.pk})

    def create(self, validated_data):
        return super().create(validated_data)
