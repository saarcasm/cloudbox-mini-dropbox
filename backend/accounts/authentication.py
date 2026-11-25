from django.contrib.auth import get_user_model
from django.core import signing
from rest_framework import authentication, exceptions
from rest_framework.authtoken.models import Token

from cloudbox.db_sync import sync_sqlite_from_s3

User = get_user_model()
TOKEN_SALT = "cloudbox-auth-v1"
TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 7  # 7 days


def issue_auth_token(user) -> str:
    """Issue a stateless HMAC-signed token valid across all serverless instances."""
    return signing.dumps({"uid": user.pk, "un": user.username}, salt=TOKEN_SALT)


class SignedTokenAuthentication(authentication.BaseAuthentication):
    """Accepts both stateless signed tokens and standard DRF database tokens."""

    keyword = "Token"

    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request).decode("utf-8")
        if not auth_header:
            return None
        parts = auth_header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            return None

        raw_token = parts[1].strip()
        if not raw_token:
            return None

        # 1. Try stateless signed token first
        try:
            payload = signing.loads(raw_token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE_SECONDS)
            user = User.objects.filter(pk=payload.get("uid"), username=payload.get("un")).first()
            if not user and sync_sqlite_from_s3(force=True):
                user = User.objects.filter(pk=payload.get("uid"), username=payload.get("un")).first()
            if user and user.is_active:
                return (user, raw_token)
        except signing.BadSignature:
            pass

        # 2. Fall back to DRF Token table
        try:
            token_obj = Token.objects.select_related("user").get(key=raw_token)
            if token_obj.user.is_active:
                return (token_obj.user, token_obj)
        except Token.DoesNotExist:
            pass

        raise exceptions.AuthenticationFailed("Invalid or expired authentication token.")
