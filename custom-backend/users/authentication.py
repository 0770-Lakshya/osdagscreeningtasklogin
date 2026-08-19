from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from .models import BlacklistedAccessToken


class RevocableJWTAuthentication(JWTAuthentication):
    """JWT auth + blacklist check for logged-out tokens"""

    def get_validated_token(self, raw_token):
        validated_token = super().get_validated_token(raw_token)
        jti = validated_token.get("jti")
        if jti and BlacklistedAccessToken.objects.filter(jti=jti).exists():
            raise InvalidToken("Token has been revoked.")
        return validated_token
