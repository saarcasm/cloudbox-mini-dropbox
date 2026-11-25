from __future__ import annotations

import io
import mimetypes
import os
import uuid
import zipfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q, Sum
from django.http import FileResponse, HttpResponse, HttpResponseRedirect
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import UserProfile
from .models import ChunkedUploadSession, Folder, ShareLink, StoredFile
from .serializers import FolderSerializer, ShareLinkSerializer, StoredFileSerializer
from .storage_backend import cleanup_dir, get_storage_driver, sanitize_filename


def _build_breadcrumbs(folder: Folder | None):
    crumbs = []
    current = folder
    seen = set()
    while current is not None and current.id not in seen:
        seen.add(current.id)
        crumbs.append({"id": str(current.id), "name": current.name})
        current = current.parent
    crumbs.reverse()
    return crumbs


def _collect_folder_subtree_ids(root_folder: Folder) -> list[uuid.UUID]:
    ids = [root_folder.id]
    queue = [root_folder.id]
    while queue:
        children = list(
            Folder.objects.filter(parent_id__in=queue).values_list("id", flat=True)
        )
        ids.extend(children)
        queue = children
    return ids


def _categorize_mime(content_type: str, filename: str) -> str:
    ct = (content_type or "").lower()
    ext = Path(filename).suffix.lower()
    if ct.startswith("image/") or ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        return "images"
    if ct.startswith("video/") or ct.startswith("audio/") or ext in {".mp4", ".mov", ".mp3", ".wav"}:
        return "media"
    if ct in {"application/pdf", "text/plain", "text/csv"} or ext in {
        ".pdf",
        ".doc",
        ".docx",
        ".txt",
        ".md",
        ".ppt",
        ".pptx",
        ".xls",
        ".xlsx",
        ".csv",
    }:
        return "documents"
    if ext in {".zip", ".tar", ".gz", ".rar", ".7z"}:
        return "archives"
    return "other"


def _check_quota(user, incoming_bytes: int) -> str | None:
    if incoming_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        return f"File exceeds the maximum allowed upload size of {max_mb} MB."
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if incoming_bytes > profile.available_storage_bytes:
        return "Not enough available storage quota for this upload."

    # Enforce AWS S3 Free Tier bucket ceiling (default 4.5 GB of 5 GB Free Tier)
    driver = get_storage_driver()
    if driver.supports_presigned and settings.S3_FREE_TIER_GUARD:
        total_bucket_bytes = StoredFile.objects.aggregate(total=Sum("size_bytes"))["total"] or 0
        if total_bucket_bytes + incoming_bytes > settings.S3_FREE_TIER_MAX_BYTES:
            return (
                "Upload paused to stay within AWS S3 Free Tier storage limit "
                f"({settings.S3_FREE_TIER_MAX_BYTES / (1024**3):.1f} GB)."
            )
    return None


def _stream_stored_file(stored_file: StoredFile, as_attachment: bool = True, url_only: bool = False):
    driver = get_storage_driver()
    if driver.supports_presigned:
        presigned_url = driver.generate_presigned_download_url(
            stored_file.object_key,
            stored_file.name,
            as_attachment=as_attachment,
        )
        if url_only:
            return Response({"download_url": presigned_url, "filename": stored_file.name})
        return HttpResponseRedirect(presigned_url)

    try:
        stream = driver.open_file(stored_file.object_key)
    except FileNotFoundError:
        return Response(
            {"detail": "File binary is missing from cloud storage bucket."},
            status=status.HTTP_404_NOT_FOUND,
        )
    response = FileResponse(
        stream,
        as_attachment=as_attachment,
        filename=sanitize_filename(stored_file.name),
        content_type=stored_file.content_type or "application/octet-stream",
    )
    response["Content-Length"] = stored_file.size_bytes
    return response


class DashboardStatsView(APIView):
    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        files = StoredFile.objects.filter(owner=request.user)
        breakdown = {"images": 0, "documents": 0, "media": 0, "archives": 0, "other": 0}
        for f in files.only("content_type", "name", "size_bytes"):
            cat = _categorize_mime(f.content_type, f.name)
            breakdown[cat] += f.size_bytes

        used_bytes = profile.used_storage_bytes
        quota_bytes = profile.storage_quota_bytes
        recent_files = StoredFileSerializer(files[:6], many=True).data
        driver = get_storage_driver()

        return Response(
            {
                "used_bytes": used_bytes,
                "quota_bytes": quota_bytes,
                "available_bytes": max(0, quota_bytes - used_bytes),
                "usage_percent": round((used_bytes / quota_bytes) * 100, 2) if quota_bytes else 0,
                "file_count": files.count(),
                "folder_count": Folder.objects.filter(owner=request.user).count(),
                "active_share_count": ShareLink.objects.filter(
                    owner=request.user, is_active=True
                ).count(),
                "storage_provider": driver.provider_name,
                "breakdown_bytes": breakdown,
                "recent_files": recent_files,
            }
        )


class DirectoryContentsView(APIView):
    def get(self, request):
        folder_id = request.query_params.get("folder")
        search_q = (request.query_params.get("q") or "").strip()

        current_folder = None
        if folder_id:
            current_folder = Folder.objects.filter(id=folder_id, owner=request.user).first()
            if not current_folder:
                return Response({"detail": "Folder not found."}, status=status.HTTP_404_NOT_FOUND)

        if search_q:
            folders = Folder.objects.filter(owner=request.user, name__icontains=search_q)
            files = StoredFile.objects.filter(owner=request.user, name__icontains=search_q)
        else:
            folders = Folder.objects.filter(owner=request.user, parent=current_folder)
            files = StoredFile.objects.filter(owner=request.user, folder=current_folder)

        return Response(
            {
                "current_folder": FolderSerializer(current_folder).data if current_folder else None,
                "breadcrumbs": _build_breadcrumbs(current_folder),
                "folders": FolderSerializer(folders, many=True).data,
                "files": StoredFileSerializer(files, many=True).data,
            }
        )


class FolderListCreateView(APIView):
    def get(self, request):
        folders = Folder.objects.filter(owner=request.user)
        return Response(FolderSerializer(folders, many=True).data)

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        parent_id = request.data.get("parent")
        if not name or "/" in name or "\\" in name:
            return Response(
                {"detail": "Provide a valid folder name without slashes."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parent = None
        if parent_id:
            parent = Folder.objects.filter(id=parent_id, owner=request.user).first()
            if not parent:
                return Response(
                    {"detail": "Parent folder not found."}, status=status.HTTP_404_NOT_FOUND
                )

        try:
            folder = Folder.objects.create(owner=request.user, name=name, parent=parent)
        except IntegrityError:
            return Response(
                {"detail": "A folder with that name already exists here."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(FolderSerializer(folder).data, status=status.HTTP_201_CREATED)


class FolderDetailView(APIView):
    def patch(self, request, folder_id):
        folder = Folder.objects.filter(id=folder_id, owner=request.user).first()
        if not folder:
            return Response({"detail": "Folder not found."}, status=status.HTTP_404_NOT_FOUND)

        new_name = (request.data.get("name") or "").strip()
        if not new_name or "/" in new_name or "\\" in new_name:
            return Response(
                {"detail": "Provide a valid folder name without slashes."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        folder.name = new_name
        try:
            folder.save(update_fields=["name", "updated_at"])
        except IntegrityError:
            return Response(
                {"detail": "A folder with that name already exists here."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(FolderSerializer(folder).data)

    def delete(self, request, folder_id):
        folder = Folder.objects.filter(id=folder_id, owner=request.user).first()
        if not folder:
            return Response({"detail": "Folder not found."}, status=status.HTTP_404_NOT_FOUND)

        subtree_ids = _collect_folder_subtree_ids(folder)
        files = list(StoredFile.objects.filter(owner=request.user, folder_id__in=subtree_ids))
        driver = get_storage_driver()
        for f in files:
            driver.delete_object(f.object_key)
        folder.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FileUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        folder_id = request.data.get("folder")
        folder = None
        if folder_id:
            folder = Folder.objects.filter(id=folder_id, owner=request.user).first()
            if not folder:
                return Response({"detail": "Folder not found."}, status=status.HTTP_404_NOT_FOUND)

        quota_err = _check_quota(request.user, upload.size)
        if quota_err:
            return Response({"detail": quota_err}, status=status.HTTP_400_BAD_REQUEST)

        clean_name = os.path.basename(upload.name) or "untitled"
        content_type = (
            upload.content_type
            or mimetypes.guess_type(clean_name)[0]
            or "application/octet-stream"
        )
        file_id = uuid.uuid4()
        object_key = f"users/{request.user.id}/{file_id}"

        driver = get_storage_driver()
        size_bytes, checksum = driver.save_file(object_key, upload.file, content_type)

        stored = StoredFile.objects.create(
            id=file_id,
            owner=request.user,
            folder=folder,
            name=clean_name,
            object_key=object_key,
            size_bytes=size_bytes,
            content_type=content_type,
            checksum_sha256=checksum,
            encrypted_at_rest=True,
        )
        return Response(StoredFileSerializer(stored).data, status=status.HTTP_201_CREATED)


class ChunkedUploadInitView(APIView):
    parser_classes = [JSONParser]

    def post(self, request):
        filename = os.path.basename((request.data.get("filename") or "").strip())
        total_size = request.data.get("total_size")
        total_chunks = request.data.get("total_chunks")
        folder_id = request.data.get("folder")
        content_type = request.data.get("content_type") or "application/octet-stream"

        if not filename:
            return Response({"detail": "filename is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            total_size = int(total_size)
            total_chunks = int(total_chunks)
            if total_size < 0 or total_chunks < 1:
                raise ValueError
        except (TypeError, ValueError):
            return Response(
                {"detail": "total_size and total_chunks must be valid positive integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        quota_err = _check_quota(request.user, total_size)
        if quota_err:
            return Response({"detail": quota_err}, status=status.HTTP_400_BAD_REQUEST)

        folder = None
        if folder_id:
            folder = Folder.objects.filter(id=folder_id, owner=request.user).first()
            if not folder:
                return Response({"detail": "Folder not found."}, status=status.HTTP_404_NOT_FOUND)

        session = ChunkedUploadSession.objects.create(
            owner=request.user,
            folder=folder,
            filename=filename,
            total_size=total_size,
            total_chunks=total_chunks,
            content_type=content_type,
        )
        session_dir = settings.CHUNK_TEMP_DIR / str(session.id)
        session_dir.mkdir(parents=True, exist_ok=True)
        return Response({"upload_id": str(session.id)}, status=status.HTTP_201_CREATED)


class ChunkedUploadChunkView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload_id = request.data.get("upload_id")
        chunk_index = request.data.get("chunk_index")
        chunk_file = request.FILES.get("chunk")

        session = ChunkedUploadSession.objects.filter(id=upload_id, owner=request.user).first()
        if not session:
            return Response(
                {"detail": "Upload session not found."}, status=status.HTTP_404_NOT_FOUND
            )
        try:
            idx = int(chunk_index)
            if idx < 0 or idx >= session.total_chunks:
                raise ValueError
        except (TypeError, ValueError):
            return Response({"detail": "Invalid chunk_index."}, status=status.HTTP_400_BAD_REQUEST)

        if not chunk_file:
            return Response({"detail": "Missing chunk payload."}, status=status.HTTP_400_BAD_REQUEST)

        session_dir = settings.CHUNK_TEMP_DIR / str(session.id)
        session_dir.mkdir(parents=True, exist_ok=True)
        chunk_path = session_dir / f"part_{idx:06d}"
        with open(chunk_path, "wb") as dest:
            for block in chunk_file.chunks():
                dest.write(block)

        return Response({"received_chunk": idx})


class ChunkedUploadCompleteView(APIView):
    parser_classes = [JSONParser]

    def post(self, request):
        upload_id = request.data.get("upload_id")
        session = ChunkedUploadSession.objects.filter(id=upload_id, owner=request.user).first()
        if not session:
            return Response(
                {"detail": "Upload session not found."}, status=status.HTTP_404_NOT_FOUND
            )

        session_dir = settings.CHUNK_TEMP_DIR / str(session.id)
        missing = [
            i for i in range(session.total_chunks) if not (session_dir / f"part_{i:06d}").exists()
        ]
        if missing:
            return Response(
                {"detail": f"Missing chunks: {missing[:5]}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assembled_path = session_dir / "assembled.bin"
        with open(assembled_path, "wb") as out:
            for i in range(session.total_chunks):
                with open(session_dir / f"part_{i:06d}", "rb") as part:
                    while True:
                        buf = part.read(1024 * 1024)
                        if not buf:
                            break
                        out.write(buf)

        actual_size = assembled_path.stat().st_size
        quota_err = _check_quota(request.user, actual_size)
        if quota_err:
            cleanup_dir(session_dir)
            session.delete()
            return Response({"detail": quota_err}, status=status.HTTP_400_BAD_REQUEST)

        file_id = uuid.uuid4()
        object_key = f"users/{request.user.id}/{file_id}"
        driver = get_storage_driver()
        with open(assembled_path, "rb") as stream:
            size_bytes, checksum = driver.save_file(object_key, stream, session.content_type)

        stored = StoredFile.objects.create(
            id=file_id,
            owner=request.user,
            folder=session.folder,
            name=session.filename,
            object_key=object_key,
            size_bytes=size_bytes,
            content_type=session.content_type
            or mimetypes.guess_type(session.filename)[0]
            or "application/octet-stream",
            checksum_sha256=checksum,
            encrypted_at_rest=True,
        )
        cleanup_dir(session_dir)
        session.delete()
        return Response(StoredFileSerializer(stored).data, status=status.HTTP_201_CREATED)


class PresignedUploadInitView(APIView):
    parser_classes = [JSONParser]

    def post(self, request):
        driver = get_storage_driver()
        if not driver.supports_presigned:
            return Response({"mode": "server"})

        filename = sanitize_filename(os.path.basename((request.data.get("filename") or "").strip()))
        total_size = request.data.get("total_size")
        folder_id = request.data.get("folder")
        content_type = (
            request.data.get("content_type")
            or mimetypes.guess_type(filename)[0]
            or "application/octet-stream"
        )

        try:
            total_size = int(total_size)
            if total_size < 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response(
                {"detail": "total_size must be a non-negative integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        quota_err = _check_quota(request.user, total_size)
        if quota_err:
            return Response({"detail": quota_err}, status=status.HTTP_400_BAD_REQUEST)

        if folder_id:
            if not Folder.objects.filter(id=folder_id, owner=request.user).exists():
                return Response({"detail": "Folder not found."}, status=status.HTTP_404_NOT_FOUND)

        file_id = uuid.uuid4()
        object_key = f"users/{request.user.id}/{file_id}"
        presigned = driver.generate_presigned_upload_url(object_key, content_type)
        return Response(
            {
                "mode": "presigned",
                "file_id": str(file_id),
                "object_key": object_key,
                "upload_url": presigned["url"],
                "headers": presigned["headers"],
            }
        )


class PresignedUploadConfirmView(APIView):
    parser_classes = [JSONParser]

    def post(self, request):
        driver = get_storage_driver()
        if not driver.supports_presigned:
            return Response(
                {"detail": "Presigned S3 mode is not active."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file_id = request.data.get("file_id")
        object_key = (request.data.get("object_key") or "").strip()
        filename = sanitize_filename(os.path.basename((request.data.get("filename") or "").strip()))
        folder_id = request.data.get("folder")
        content_type = (
            request.data.get("content_type")
            or mimetypes.guess_type(filename)[0]
            or "application/octet-stream"
        )

        expected_prefix = f"users/{request.user.id}/"
        if not object_key.startswith(expected_prefix):
            return Response({"detail": "Invalid object key."}, status=status.HTTP_403_FORBIDDEN)

        try:
            parsed_file_id = uuid.UUID(str(file_id))
        except (TypeError, ValueError):
            return Response({"detail": "Invalid file_id."}, status=status.HTTP_400_BAD_REQUEST)

        if object_key != f"{expected_prefix}{parsed_file_id}":
            return Response({"detail": "Mismatched file_id and object_key."}, status=status.HTTP_400_BAD_REQUEST)

        folder = None
        if folder_id:
            folder = Folder.objects.filter(id=folder_id, owner=request.user).first()
            if not folder:
                return Response({"detail": "Folder not found."}, status=status.HTTP_404_NOT_FOUND)

        meta = driver.head_object(object_key)
        if not meta:
            return Response(
                {"detail": "Uploaded object not found in S3 bucket."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        actual_size = int(meta["size_bytes"])
        quota_err = _check_quota(request.user, actual_size)
        if quota_err:
            driver.delete_object(object_key)
            return Response({"detail": quota_err}, status=status.HTTP_400_BAD_REQUEST)

        stored = StoredFile.objects.create(
            id=parsed_file_id,
            owner=request.user,
            folder=folder,
            name=filename,
            object_key=object_key,
            size_bytes=actual_size,
            content_type=content_type,
            checksum_sha256=str(meta.get("etag") or "")[:64],
            encrypted_at_rest=True,
        )
        return Response(StoredFileSerializer(stored).data, status=status.HTTP_201_CREATED)


class FileDownloadView(APIView):
    def get(self, request, file_id):
        stored = StoredFile.objects.filter(id=file_id, owner=request.user).first()
        if not stored:
            return Response({"detail": "File not found."}, status=status.HTTP_404_NOT_FOUND)
        as_attachment = request.query_params.get("inline") != "1"
        url_only = request.query_params.get("url_only") == "1"
        return _stream_stored_file(stored, as_attachment=as_attachment, url_only=url_only)


class FileRenameView(APIView):
    def patch(self, request, file_id):
        stored = StoredFile.objects.filter(id=file_id, owner=request.user).first()
        if not stored:
            return Response({"detail": "File not found."}, status=status.HTTP_404_NOT_FOUND)

        new_name = os.path.basename((request.data.get("name") or "").strip())
        if not new_name:
            return Response(
                {"detail": "Provide a valid file name."}, status=status.HTTP_400_BAD_REQUEST
            )

        stored.name = new_name
        stored.save(update_fields=["name", "updated_at"])
        return Response(StoredFileSerializer(stored).data)


class FileDeleteView(APIView):
    def delete(self, request, file_id):
        stored = StoredFile.objects.filter(id=file_id, owner=request.user).first()
        if not stored:
            return Response({"detail": "File not found."}, status=status.HTTP_404_NOT_FOUND)
        driver = get_storage_driver()
        driver.delete_object(stored.object_key)
        stored.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShareLinkListCreateView(APIView):
    def get(self, request):
        links = ShareLink.objects.filter(owner=request.user).select_related("file", "folder")
        return Response(ShareLinkSerializer(links, many=True).data)

    def post(self, request):
        file_id = request.data.get("file_id")
        folder_id = request.data.get("folder_id")
        expires_hours = request.data.get("expires_hours")

        if bool(file_id) == bool(folder_id):
            return Response(
                {"detail": "Specify exactly one of file_id or folder_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_file = None
        target_folder = None
        if file_id:
            target_file = StoredFile.objects.filter(id=file_id, owner=request.user).first()
            if not target_file:
                return Response({"detail": "File not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            target_folder = Folder.objects.filter(id=folder_id, owner=request.user).first()
            if not target_folder:
                return Response({"detail": "Folder not found."}, status=status.HTTP_404_NOT_FOUND)

        expires_at = None
        if expires_hours:
            try:
                hours = int(expires_hours)
                if hours > 0:
                    expires_at = timezone.now() + timedelta(hours=hours)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "expires_hours must be a positive integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Reuse active non-expired link if no explicit new expiry was requested
        existing = ShareLink.objects.filter(
            owner=request.user, file=target_file, folder=target_folder, is_active=True
        ).first()
        if existing and existing.is_accessible and expires_at is None:
            return Response(ShareLinkSerializer(existing).data, status=status.HTTP_200_OK)

        link = ShareLink.objects.create(
            owner=request.user,
            file=target_file,
            folder=target_folder,
            expires_at=expires_at,
        )
        return Response(ShareLinkSerializer(link).data, status=status.HTTP_201_CREATED)


class ShareLinkDetailView(APIView):
    def patch(self, request, share_id):
        link = ShareLink.objects.filter(id=share_id, owner=request.user).first()
        if not link:
            return Response({"detail": "Share link not found."}, status=status.HTTP_404_NOT_FOUND)
        if "is_active" in request.data:
            link.is_active = bool(request.data["is_active"])
            link.save(update_fields=["is_active"])
        return Response(ShareLinkSerializer(link).data)

    def delete(self, request, share_id):
        link = ShareLink.objects.filter(id=share_id, owner=request.user).first()
        if not link:
            return Response({"detail": "Share link not found."}, status=status.HTTP_404_NOT_FOUND)
        link.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _get_accessible_share_or_404(token: str):
    link = (
        ShareLink.objects.select_related("file", "folder", "owner")
        .filter(token=token)
        .first()
    )
    if not link or not link.is_accessible:
        return None
    return link


class PublicShareDetailView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, token):
        link = _get_accessible_share_or_404(token)
        if not link:
            return Response(
                {"detail": "Share link is invalid, revoked, or expired."},
                status=status.HTTP_404_NOT_FOUND,
            )

        payload = {
            "token": link.token,
            "owner": link.owner.username,
            "target_type": "file" if link.file else "folder",
            "expires_at": link.expires_at,
            "download_count": link.download_count,
            "created_at": link.created_at,
        }
        if link.file:
            payload["file"] = {
                "id": str(link.file.id),
                "name": link.file.name,
                "size_bytes": link.file.size_bytes,
                "content_type": link.file.content_type,
                "checksum_sha256": link.file.checksum_sha256,
            }
        else:
            subtree_ids = _collect_folder_subtree_ids(link.folder)
            folder_files = StoredFile.objects.filter(
                owner=link.owner, folder_id__in=subtree_ids
            ).order_by("name")
            payload["folder"] = {
                "id": str(link.folder.id),
                "name": link.folder.name,
                "files": [
                    {
                        "id": str(f.id),
                        "name": f.name,
                        "size_bytes": f.size_bytes,
                        "content_type": f.content_type,
                    }
                    for f in folder_files
                ],
            }
        return Response(payload)


class PublicShareDownloadView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, token):
        link = _get_accessible_share_or_404(token)
        if not link:
            return Response(
                {"detail": "Share link is invalid, revoked, or expired."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if link.file:
            ShareLink.objects.filter(pk=link.pk).update(download_count=F("download_count") + 1)
            return _stream_stored_file(link.file, as_attachment=True)

        # Shared folder: download either a specific file inside the subtree or a zip of the folder
        subtree_ids = _collect_folder_subtree_ids(link.folder)
        requested_file_id = request.query_params.get("file_id")
        if requested_file_id:
            target = StoredFile.objects.filter(
                id=requested_file_id, owner=link.owner, folder_id__in=subtree_ids
            ).first()
            if not target:
                return Response(
                    {"detail": "Requested file is not part of this shared folder."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            ShareLink.objects.filter(pk=link.pk).update(download_count=F("download_count") + 1)
            return _stream_stored_file(target, as_attachment=True)

        # Build a zip archive of all files in the shared folder subtree
        files = list(StoredFile.objects.filter(owner=link.owner, folder_id__in=subtree_ids))
        driver = get_storage_driver()
        zip_buffer = io.BytesIO()
        used_names = {}
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                try:
                    with driver.open_file(f.object_key) as fh:
                        arcname = f.name
                        if arcname in used_names:
                            used_names[arcname] += 1
                            stem = Path(arcname).stem
                            suffix = Path(arcname).suffix
                            arcname = f"{stem}_{used_names[arcname]}{suffix}"
                        else:
                            used_names[arcname] = 0
                        zf.writestr(arcname, fh.read())
                except FileNotFoundError:
                    continue

        ShareLink.objects.filter(pk=link.pk).update(download_count=F("download_count") + 1)
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
        safe_zip_name = sanitize_filename(link.folder.name)
        response["Content-Disposition"] = f'attachment; filename="{safe_zip_name}.zip"'
        return response
