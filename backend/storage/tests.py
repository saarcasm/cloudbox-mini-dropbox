import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserProfile

User = get_user_model()


class FakeS3Driver:
    provider_name = "AWS S3 (Free Tier)"
    supports_presigned = True

    def __init__(self):
        self.objects = {}

    def generate_presigned_upload_url(self, object_key, content_type, expires_in=300):
        return {
            "url": f"https://fake-s3.amazonaws.com/{object_key}?sig=put",
            "headers": {"Content-Type": content_type, "x-amz-server-side-encryption": "AES256"},
        }

    def generate_presigned_download_url(self, object_key, filename, as_attachment=True, expires_in=300):
        return f"https://fake-s3.amazonaws.com/{object_key}?filename={filename}"

    def head_object(self, object_key):
        return self.objects.get(object_key)

    def delete_object(self, object_key):
        self.objects.pop(object_key, None)


class CloudBoxAPITests(APITestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="cloudbox_test_"))
        self.bucket_dir = self.temp_dir / "bucket"
        self.chunk_dir = self.temp_dir / "chunks"
        self.override = override_settings(
            LOCAL_BUCKET_DIR=self.bucket_dir,
            CHUNK_TEMP_DIR=self.chunk_dir,
            USE_S3=False,
        )
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _register_and_auth(self, username="saar", email="saar@example.com", password="password123"):
        resp = self.client.post(
            "/api/auth/register/",
            {"username": username, "email": email, "password": password},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        token = resp.data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        return resp.data["user"]

    def test_upload_rename_download_delete_and_quota(self):
        self._register_and_auth()

        # Create folder
        folder_resp = self.client.post("/api/storage/folders/", {"name": "CSE Notes"}, format="json")
        self.assertEqual(folder_resp.status_code, status.HTTP_201_CREATED)
        folder_id = folder_resp.data["id"]

        # Upload file
        sample = SimpleUploadedFile("lecture1.txt", b"CloudBox Mini Dropbox", content_type="text/plain")
        upload_resp = self.client.post(
            "/api/storage/files/upload/",
            {"file": sample, "folder": folder_id},
            format="multipart",
        )
        self.assertEqual(upload_resp.status_code, status.HTTP_201_CREATED)
        file_id = upload_resp.data["id"]
        self.assertEqual(upload_resp.data["size_bytes"], 21)

        # Dashboard shows updated used storage
        dash_resp = self.client.get("/api/storage/dashboard/")
        self.assertEqual(dash_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(dash_resp.data["used_bytes"], 21)
        self.assertEqual(dash_resp.data["file_count"], 1)
        self.assertEqual(dash_resp.data["folder_count"], 1)

        # Rename file
        rename_resp = self.client.patch(
            f"/api/storage/files/{file_id}/rename/",
            {"name": "cloud_notes.txt"},
            format="json",
        )
        self.assertEqual(rename_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(rename_resp.data["name"], "cloud_notes.txt")

        # Download file (attachment) & preview (inline)
        dl_resp = self.client.get(f"/api/storage/files/{file_id}/download/")
        self.assertEqual(dl_resp.status_code, status.HTTP_200_OK)
        self.assertIn("attachment", dl_resp["Content-Disposition"])
        self.assertEqual(b"".join(dl_resp.streaming_content), b"CloudBox Mini Dropbox")

        inline_resp = self.client.get(f"/api/storage/files/{file_id}/download/?inline=1")
        self.assertEqual(inline_resp.status_code, status.HTTP_200_OK)
        self.assertIn("inline", inline_resp["Content-Disposition"])
        self.assertEqual(b"".join(inline_resp.streaming_content), b"CloudBox Mini Dropbox")

        # Delete file
        del_resp = self.client.delete(f"/api/storage/files/{file_id}/")
        self.assertEqual(del_resp.status_code, status.HTTP_204_NO_CONTENT)

        dash_after = self.client.get("/api/storage/dashboard/")
        self.assertEqual(dash_after.data["used_bytes"], 0)

    def test_chunked_upload_and_public_share_link_permissions(self):
        self._register_and_auth("rohan", "rohan@example.com")

        # Chunked upload (2 chunks)
        payload = b"Hello " + b"World from CloudBox!"
        init_resp = self.client.post(
            "/api/storage/files/upload/init/",
            {
                "filename": "report.txt",
                "total_size": len(payload),
                "total_chunks": 2,
                "content_type": "text/plain",
            },
            format="json",
        )
        self.assertEqual(init_resp.status_code, status.HTTP_201_CREATED)
        upload_id = init_resp.data["upload_id"]

        c0 = SimpleUploadedFile("chunk0", payload[:6])
        c1 = SimpleUploadedFile("chunk1", payload[6:])
        self.assertEqual(
            self.client.post(
                "/api/storage/files/upload/chunk/",
                {"upload_id": upload_id, "chunk_index": 0, "chunk": c0},
                format="multipart",
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.post(
                "/api/storage/files/upload/chunk/",
                {"upload_id": upload_id, "chunk_index": 1, "chunk": c1},
                format="multipart",
            ).status_code,
            status.HTTP_200_OK,
        )
        complete_resp = self.client.post(
            "/api/storage/files/upload/complete/", {"upload_id": upload_id}, format="json"
        )
        self.assertEqual(complete_resp.status_code, status.HTTP_201_CREATED)
        file_id = complete_resp.data["id"]

        # Create share link
        share_resp = self.client.post(
            "/api/storage/shares/", {"file_id": file_id}, format="json"
        )
        self.assertEqual(share_resp.status_code, status.HTTP_201_CREATED)
        share_id = share_resp.data["id"]
        token = share_resp.data["token"]

        # Anonymous user can inspect and download via share link
        self.client.credentials()
        pub_detail = self.client.get(f"/api/share/{token}/")
        self.assertEqual(pub_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(pub_detail.data["file"]["name"], "report.txt")

        pub_dl = self.client.get(f"/api/share/{token}/download/")
        self.assertEqual(pub_dl.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(pub_dl.streaming_content), payload)

        # Another user cannot download private file directly
        self._register_and_auth("saksham", "saksham@example.com")
        unauth_dl = self.client.get(f"/api/storage/files/{file_id}/download/")
        self.assertEqual(unauth_dl.status_code, status.HTTP_404_NOT_FOUND)

        # Owner revokes share link -> anonymous download blocked
        login_rohan = self.client.post(
            "/api/auth/login/", {"username": "rohan", "password": "password123"}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {login_rohan.data['token']}")
        revoke_resp = self.client.patch(
            f"/api/storage/shares/{share_id}/", {"is_active": False}, format="json"
        )
        self.assertEqual(revoke_resp.status_code, status.HTTP_200_OK)

        self.client.credentials()
        revoked_dl = self.client.get(f"/api/share/{token}/download/")
        self.assertEqual(revoked_dl.status_code, status.HTTP_404_NOT_FOUND)

    def test_quota_limit_blocks_oversized_upload(self):
        user_data = self._register_and_auth("quotauser", "quota@example.com")
        profile = UserProfile.objects.get(user_id=user_data["id"])
        profile.storage_quota_bytes = 10
        profile.save()

        big_file = SimpleUploadedFile("too_big.bin", b"0123456789abcdef")
        resp = self.client.post("/api/storage/files/upload/", {"file": big_file}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_folder_share_zip_download_and_admin_quota(self):
        self._register_and_auth("alice", "alice@example.com")
        folder_resp = self.client.post("/api/storage/folders/", {"name": "ProjectDocs"}, format="json")
        self.assertEqual(folder_resp.status_code, status.HTTP_201_CREATED)
        folder_id = folder_resp.data["id"]

        f1 = SimpleUploadedFile("readme.txt", b"Hello CloudBox")
        self.client.post(
            "/api/storage/files/upload/", {"file": f1, "folder": folder_id}, format="multipart"
        )

        # Share folder
        share_resp = self.client.post(
            "/api/storage/shares/", {"folder_id": folder_id}, format="json"
        )
        self.assertEqual(share_resp.status_code, status.HTTP_201_CREATED)
        token = share_resp.data["token"]

        # Anonymous zip download of shared folder
        self.client.credentials()
        detail = self.client.get(f"/api/share/{token}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(len(detail.data["folder"]["files"]), 1)

        zip_resp = self.client.get(f"/api/share/{token}/download/")
        self.assertEqual(zip_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(zip_resp["Content-Type"], "application/zip")

        # Staff user can update quota via admin API
        staff = User.objects.create_user(
            username="adminuser", email="admin@example.com", password="password123", is_staff=True
        )
        login_resp = self.client.post(
            "/api/auth/login/", {"username": staff.username, "password": "password123"}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {login_resp.data['token']}")
        alice = User.objects.get(username="alice")
        quota_resp = self.client.patch(
            f"/api/auth/admin/users/{alice.id}/quota/", {"quota_mb": 1024}, format="json"
        )
        self.assertEqual(quota_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(quota_resp.data["quota_bytes"], 1024 * 1024 * 1024)

    def test_s3_presigned_upload_download_and_free_tier_guard(self):
        self._register_and_auth("s3user", "s3@example.com")
        fake_s3 = FakeS3Driver()

        with patch("storage.views.get_storage_driver", return_value=fake_s3):
            with override_settings(S3_FREE_TIER_GUARD=True, S3_FREE_TIER_MAX_BYTES=100):
                # Exceeding Free Tier guard is blocked at presign
                blocked = self.client.post(
                    "/api/storage/files/upload/presign/",
                    {"filename": "huge.zip", "total_size": 150, "content_type": "application/zip"},
                    format="json",
                )
                self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)

                # Valid presign under Free Tier limit
                presign = self.client.post(
                    "/api/storage/files/upload/presign/",
                    {"filename": "notes.txt", "total_size": 40, "content_type": "text/plain"},
                    format="json",
                )
                self.assertEqual(presign.status_code, status.HTTP_200_OK)
                self.assertEqual(presign.data["mode"], "presigned")
                self.assertIn("https://fake-s3.amazonaws.com/", presign.data["upload_url"])

                # Simulate S3 PUT landing in bucket
                obj_key = presign.data["object_key"]
                fake_s3.objects[obj_key] = {"size_bytes": 40, "etag": "abc123"}

                confirm = self.client.post(
                    "/api/storage/files/upload/confirm/",
                    {
                        "file_id": presign.data["file_id"],
                        "object_key": obj_key,
                        "filename": "notes.txt",
                        "content_type": "text/plain",
                    },
                    format="json",
                )
                self.assertEqual(confirm.status_code, status.HTTP_201_CREATED)
                file_id = confirm.data["id"]

                # Presigned download URL
                dl_json = self.client.get(f"/api/storage/files/{file_id}/download/?url_only=1")
                self.assertEqual(dl_json.status_code, status.HTTP_200_OK)
                self.assertIn("https://fake-s3.amazonaws.com/", dl_json.data["download_url"])

                # Direct 302 redirect download
                dl_redirect = self.client.get(f"/api/storage/files/{file_id}/download/")
                self.assertEqual(dl_redirect.status_code, status.HTTP_302_FOUND)

    def test_case_insensitive_login_email_and_signed_token(self):
        # Reject username with spaces cleanly
        bad = self.client.post(
            "/api/auth/register/",
            {"username": "bad user", "email": "bad@example.com", "password": "password123"},
            format="json",
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        self._register_and_auth("SaarTest", "saartest@example.com", "password123")
        self.client.credentials()

        # Login with different-case username
        u_login = self.client.post(
            "/api/auth/login/",
            {"username": "saartest", "password": "password123"},
            format="json",
        )
        self.assertEqual(u_login.status_code, status.HTTP_200_OK)
        token = u_login.data["token"]
        self.assertGreaterEqual(len(token.split(":")), 3)

        # Login with different-case email
        e_login = self.client.post(
            "/api/auth/login/",
            {"username": "SAARTEST@EXAMPLE.COM", "password": "password123"},
            format="json",
        )
        self.assertEqual(e_login.status_code, status.HTTP_200_OK)

        # Signed token authenticates on /api/auth/me/ without needing DB Token rows
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {e_login.data['token']}")
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data["username"], "SaarTest")


