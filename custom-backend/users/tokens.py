from rest_framework_simplejwt.tokens import AccessToken

from .models import RefreshSession


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or None


def issue_token_pair(user, request):
    access = AccessToken.for_user(user)
    session, refresh_raw = RefreshSession.issue(
        user,
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    return str(access), refresh_raw, session
