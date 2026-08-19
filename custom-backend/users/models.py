import hashlib
import secrets

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField("email address", unique=True)
    full_name = models.CharField("full name", max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class RefreshSession(models.Model):
    # store the hash, not the raw token — db should never have plaintext secrets
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="refresh_sessions",
    )
    token_hash=models.CharField(max_length=64, unique=True)
    created_at=models.DateTimeField(default=timezone.now)
    expires_at=models.DateTimeField()
    ip_address=models.GenericIPAddressField(null=True, blank=True)
    user_agent=models.CharField(max_length=300, blank=True)

    @staticmethod
    def hash_token(raw):
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def issue(cls, user, ip_address=None, user_agent=""):
        raw = secrets.token_urlsafe(48)
        session = cls.objects.create(
            user=user,
            token_hash=cls.hash_token(raw),
            expires_at=timezone.now() + settings.REFRESH_TOKEN_LIFETIME,
            ip_address=ip_address,
            user_agent=user_agent[:300],
        )
        return session, raw

    @classmethod
    def consume(cls, raw):
        """single-use: looks up and deletes the session"""
        try:
            session = cls.objects.select_related("user").get(
                token_hash=cls.hash_token(raw)
            )
        except cls.DoesNotExist:
            return None
        session.delete()
        return session


class BlacklistedAccessToken(models.Model):
    # jti of logged-out access tokens
    jti = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        related_name="blacklisted_tokens",
    )
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)

    @classmethod
    def blacklist(cls, user, jti, expires_at):
        if not jti:
            return
        cls.objects.get_or_create(
            jti=jti, defaults={"user": user, "expires_at": expires_at}
        )
        # clean up old entries so the table doesn't grow forever
        cls.objects.filter(expires_at__lt=timezone.now()).delete()


class FailedLoginAttempt(models.Model):
    email = models.EmailField(db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("email", "ip_address")
