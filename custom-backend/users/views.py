from datetime import timezone as dt_timezone

from django.conf import settings
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BlacklistedAccessToken, RefreshSession
from .serializers import RegisterSerializer, UserSerializer
from .throttle import is_locked, register_failure, register_success
from .tokens import get_client_ip, issue_token_pair

# generic error — never tell the client whether the email exists or not
GENERIC_LOGIN_ERROR = "Invalid email or password."


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        access, refresh, _ = issue_token_pair(user, request)
        return Response(
            {
                "user": UserSerializer(user).data,
                "access": access,
                "refresh": refresh,
                # "token" is just an alias for access — the index.html
                # client reads body.token to auto-fill the token input
                "token": access,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        password = request.data.get("password") or ""
        ip = get_client_ip(request)

        # check lockout first
        if is_locked(email, ip):
            return Response(
                {"detail": settings.GENERIC_LOCKOUT_MESSAGE},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        user = authenticate(request, email=email, password=password)

        if user is None:
            register_failure(email, ip)
            # same error whether email exists or not
            return Response(
                {"detail": GENERIC_LOGIN_ERROR},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        register_success(email, ip)
        access, refresh, _ = issue_token_pair(user, request)
        return Response(
            {
                "user": UserSerializer(user).data,
                "access": access,
                "refresh": refresh,
                "token": access,
            }
        )


class RefreshView(APIView):
    """exchange refresh token for a new pair"""

    permission_classes = [AllowAny]

    def post(self, request):
        raw = (request.data.get("refresh") or "").strip()
        if not raw:
            return Response(
                {"detail": "refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session = RefreshSession.consume(raw)

        if (
            session is None
            or session.expires_at <= timezone.now()
            or not session.user.is_active
        ):
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        access, new_refresh, _ = issue_token_pair(session.user, request)
        return Response({"access": access, "refresh": new_refresh})


class LogoutView(APIView):
    """
    Server-side logout:
    1. delete the refresh session row
    2. blacklist the access token jti
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw = (request.data.get("refresh") or "").strip()
        if raw:
            RefreshSession.objects.filter(
                user=request.user, token_hash=RefreshSession.hash_token(raw)
            ).delete()

        access_token = request.auth
        if access_token is not None:
            BlacklistedAccessToken.blacklist(
                request.user,
                access_token.get("jti"),
                timezone.datetime.fromtimestamp(
                    access_token.get("exp"), tz=dt_timezone.utc
                ),
            )

        return Response({"detail": "Logged out."}, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # always returns the authenticated user's own data
        # no way to query another user's profile through this endpoint
        return Response(UserSerializer(request.user).data)
