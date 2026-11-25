from django.contrib.auth import authenticate, get_user_model
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from cloudbox.db_sync import sync_sqlite_from_s3
from .authentication import issue_auth_token
from .models import UserProfile
from .serializers import RegisterSerializer, UserSerializer

User = get_user_model()


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        sync_sqlite_from_s3(force=True)
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        if "username" in data and isinstance(data["username"], str):
            data["username"] = data["username"].strip()
        if "email" in data and isinstance(data["email"], str):
            data["email"] = data["email"].strip()

        serializer = RegisterSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token = issue_auth_token(user)
        return Response(
            {"token": token, "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        identifier = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""

        def _find_username(ident: str) -> str:
            if not ident:
                return ""
            if "@" in ident:
                matched = User.objects.filter(email__iexact=ident).first()
                if matched:
                    return matched.username
            matched = User.objects.filter(username__iexact=ident).first()
            return matched.username if matched else ident

        resolved_username = _find_username(identifier)
        user = authenticate(username=resolved_username, password=password)
        if not user:
            # Refresh SQLite from S3 in case the user just registered on another Lambda
            if sync_sqlite_from_s3(force=True):
                resolved_username = _find_username(identifier)
                user = authenticate(username=resolved_username, password=password)

        if not user:
            return Response(
                {"detail": "Invalid username/email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        token = issue_auth_token(user)
        return Response({"token": token, "user": UserSerializer(user).data})


class LogoutView(APIView):
    def post(self, request):
        if hasattr(request.auth, "delete"):
            request.auth.delete()
        return Response({"detail": "Logged out successfully."})


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class AdminUserListView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        users = User.objects.all().order_by("-date_joined")
        return Response({"users": UserSerializer(users, many=True).data})


class AdminUpdateQuotaView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def patch(self, request, user_id):
        target = User.objects.filter(pk=user_id).first()
        if not target:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        quota_mb = request.data.get("quota_mb")
        try:
            quota_mb = int(quota_mb)
            if quota_mb < 1:
                raise ValueError
        except (TypeError, ValueError):
            return Response(
                {"detail": "quota_mb must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile, _ = UserProfile.objects.get_or_create(user=target)
        profile.storage_quota_bytes = quota_mb * 1024 * 1024
        profile.save(update_fields=["storage_quota_bytes"])
        return Response(UserSerializer(target).data)
