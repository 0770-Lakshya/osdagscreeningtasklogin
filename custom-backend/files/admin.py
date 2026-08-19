from django.contrib import admin

from .models import UserFile


@admin.register(UserFile)
class UserFileAdmin(admin.ModelAdmin):
    list_display=("name","owner","size","uploaded_at")
    search_fields=("name", "owner__email")
    list_filter=("uploaded_at",)
