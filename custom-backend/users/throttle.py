from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import FailedLoginAttempt


def is_locked(email, ip_address):
    if not email:
        return None
    try:
        record = FailedLoginAttempt.objects.get(
            email=email.lower(), ip_address=ip_address
        )
    except FailedLoginAttempt.DoesNotExist:
        return None
    if record.locked_until and record.locked_until > timezone.now():
        return record.locked_until
    return None


def register_failure(email, ip_address):
    record, _ = FailedLoginAttempt.objects.get_or_create(
        email=email.lower(), ip_address=ip_address
    )
    record.attempts += 1
    if record.attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
        record.locked_until = timezone.now() + timedelta(
            minutes=settings.LOGIN_LOCKOUT_MINUTES
        )
        record.attempts = 0
    record.last_attempt_at = timezone.now()
    record.save(update_fields=["attempts", "locked_until", "last_attempt_at"])


def register_success(email, ip_address):
    FailedLoginAttempt.objects.filter(
        email=email.lower(), ip_address=ip_address
    ).delete()
