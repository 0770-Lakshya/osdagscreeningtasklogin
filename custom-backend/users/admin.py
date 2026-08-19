from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import BlacklistedAccessToken, FailedLoginAttempt, RefreshSession, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering=("email",)
    list_display=("email", "full_name", "is_staff", "is_active", "date_joined")
    search_fields=("email", "full_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("full_name",)}),
        (
            _("Permissions"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets=(
        (
            None,
            {"classes": ("wide",), "fields": ("email", "full_name", "password1", "password2")},
        ),
    )


@admin.register(RefreshSession)
class RefreshSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "ip_address")
    search_fields = ("user__email",)


@admin.register(BlacklistedAccessToken)
class BlacklistedAccessTokenAdmin(admin.ModelAdmin):
    list_display=("jti", "user", "created_at", "expires_at")
    search_fields=("jti", "user__email")


@admin.register(FailedLoginAttempt)
class FailedLoginAttemptAdmin(admin.ModelAdmin):
    list_display=("email", "ip_address", "attempts", "locked_until", "last_attempt_at")
