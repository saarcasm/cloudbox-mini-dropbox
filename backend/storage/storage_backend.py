"""Unified cloud storage driver supporting AWS S3 (Free Tier ready) and local bucket."""

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional, Tuple

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[\r\n"\\;/]+', "_", (name or "file").strip())
    return cleaned[:200] or "file"


class BaseStorageDriver:
    provider_name = "base"
    supports_presigned = False

    def save_file(self, object_key: str, file_obj: BinaryIO, content_type: str) -> Tuple[int, str]:
        raise NotImplementedError

    def open_file(self, object_key: str) -> BinaryIO:
        raise NotImplementedError

    def delete_object(self, object_key: str) -> None:
        raise NotImplementedError

    def head_object(self, object_key: str) -> Optional[Dict[str, object]]:
        return None


class LocalBucketStorageDriver(BaseStorageDriver):
    provider_name = "Local S3-Compatible Bucket"
    supports_presigned = False

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_key(self, object_key: str) -> Path:
        clean_key = object_key.lstrip("/")
        target = (self.root_dir / clean_key).resolve()
        if self.root_dir != target and self.root_dir not in target.parents:
            raise ValueError("Invalid storage object key")
        return target

    def save_file(self, object_key: str, file_obj: BinaryIO, content_type: str) -> Tuple[int, str]:
        target = self._resolve_key(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        hasher = hashlib.sha256()
        total_bytes = 0
        file_obj.seek(0)
        with open(target, "wb") as dest:
            while True:
                chunk = file_obj.read(1024 * 1024)
                if not chunk:
                    break
                dest.write(chunk)
                hasher.update(chunk)
                total_bytes += len(chunk)
        return total_bytes, hasher.hexdigest()

    def open_file(self, object_key: str) -> BinaryIO:
        target = self._resolve_key(object_key)
        if not target.exists():
            raise FileNotFoundError(f"Object not found in bucket: {object_key}")
        return open(target, "rb")

    def delete_object(self, object_key: str) -> None:
        target = self._resolve_key(object_key)
        if target.exists():
            target.unlink()

    def head_object(self, object_key: str) -> Optional[Dict[str, object]]:
        target = self._resolve_key(object_key)
        if not target.exists():
            return None
        return {"size_bytes": target.stat().st_size, "etag": ""}


class S3StorageDriver(BaseStorageDriver):
    provider_name = "AWS S3 (Free Tier)"
    supports_presigned = True

    def __init__(self):
        self.bucket = settings.AWS_STORAGE_BUCKET_NAME
        self.region = settings.AWS_S3_REGION_NAME
        endpoint = f"https://s3.{self.region}.amazonaws.com" if self.region else None
        self.client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=self.region,
            endpoint_url=endpoint,
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )

    def save_file(self, object_key: str, file_obj: BinaryIO, content_type: str) -> Tuple[int, str]:
        hasher = hashlib.sha256()
        total_bytes = 0
        file_obj.seek(0)
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
            total_bytes += len(chunk)

        file_obj.seek(0)
        self.client.upload_fileobj(
            file_obj,
            self.bucket,
            object_key,
            ExtraArgs={
                "ContentType": content_type or "application/octet-stream",
                "ServerSideEncryption": "AES256",
            },
        )
        return total_bytes, hasher.hexdigest()

    def open_file(self, object_key: str) -> BinaryIO:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=object_key)
            return response["Body"]
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"NoSuchKey", "404"}:
                raise FileNotFoundError(f"Object not found in S3: {object_key}") from exc
            raise

    def delete_object(self, object_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=object_key)

    def head_object(self, object_key: str) -> Optional[Dict[str, object]]:
        try:
            resp = self.client.head_object(Bucket=self.bucket, Key=object_key)
            return {
                "size_bytes": int(resp.get("ContentLength", 0)),
                "etag": (resp.get("ETag") or "").strip('"'),
                "content_type": resp.get("ContentType") or "application/octet-stream",
            }
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"NoSuchKey", "404", "NotFound"}:
                return None
            raise

    def generate_presigned_upload_url(
        self, object_key: str, content_type: str, expires_in: int = 300
    ) -> Dict[str, object]:
        ct = content_type or "application/octet-stream"
        url = self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": object_key,
                "ContentType": ct,
                "ServerSideEncryption": "AES256",
            },
            ExpiresIn=expires_in,
        )
        return {
            "url": url,
            "headers": {
                "Content-Type": ct,
                "x-amz-server-side-encryption": "AES256",
            },
        }

    def generate_presigned_download_url(
        self,
        object_key: str,
        filename: str,
        as_attachment: bool = True,
        expires_in: int = 300,
    ) -> str:
        safe = sanitize_filename(filename)
        disposition_type = "attachment" if as_attachment else "inline"
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": object_key,
                "ResponseContentDisposition": f'{disposition_type}; filename="{safe}"',
            },
            ExpiresIn=expires_in,
        )

    def ensure_bucket_configured(self, allowed_origins: List[str]) -> None:
        """Create bucket if missing and apply Free-Tier-safe privacy, AES-256, and CORS."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            create_kwargs = {"Bucket": self.bucket}
            if self.region and self.region != "us-east-1":
                create_kwargs["CreateBucketConfiguration"] = {
                    "LocationConstraint": self.region
                }
            self.client.create_bucket(**create_kwargs)

        self.client.put_public_access_block(
            Bucket=self.bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
        self.client.put_bucket_encryption(
            Bucket=self.bucket,
            ServerSideEncryptionConfiguration={
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"},
                        "BucketKeyEnabled": True,
                    }
                ]
            },
        )
        self.client.put_bucket_cors(
            Bucket=self.bucket,
            CORSConfiguration={
                "CORSRules": [
                    {
                        "AllowedHeaders": ["*"],
                        "AllowedMethods": ["GET", "PUT", "HEAD"],
                        "AllowedOrigins": allowed_origins,
                        "ExposeHeaders": ["ETag", "Content-Length", "Content-Disposition"],
                        "MaxAgeSeconds": 3600,
                    }
                ]
            },
        )


def get_storage_driver() -> BaseStorageDriver:
    if settings.USE_S3 and settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        return S3StorageDriver()
    return LocalBucketStorageDriver(settings.LOCAL_BUCKET_DIR)


def cleanup_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
