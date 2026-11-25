"""Lightweight S3-backed SQLite synchronization for stateless Vercel deployments."""

import os
import threading
import time
from pathlib import Path

from django.conf import settings
from django.db import connections

S3_DB_KEY = "_internal/cloudbox.sqlite3"
_sync_lock = threading.Lock()
_last_sync_ts = 0.0
_last_etag = None


def is_s3_sqlite_sync_enabled() -> bool:
    return bool(
        settings.IS_VERCEL
        and settings.USE_S3
        and settings.AWS_ACCESS_KEY_ID
        and settings.AWS_SECRET_ACCESS_KEY
        and not settings.DATABASE_URL
        and settings.DATABASES["default"]["ENGINE"].endswith("sqlite3")
    )


def _get_s3_driver():
    from storage.storage_backend import S3StorageDriver

    return S3StorageDriver()


def sync_sqlite_from_s3(force: bool = False) -> bool:
    """Download SQLite DB from S3 if newer than local copy. Returns True if downloaded."""
    global _last_sync_ts, _last_etag
    if not is_s3_sqlite_sync_enabled():
        return False

    now = time.time()
    if not force and (now - _last_sync_ts) < 2.5:
        return False

    with _sync_lock:
        if not force and (time.time() - _last_sync_ts) < 2.5:
            return False

        driver = _get_s3_driver()
        meta = driver.head_object(S3_DB_KEY)
        _last_sync_ts = time.time()
        db_path = Path(settings.DATABASES["default"]["NAME"])
        db_path.parent.mkdir(parents=True, exist_ok=True)

        if not meta:
            return False

        remote_etag = meta.get("etag")
        if not force and db_path.exists() and remote_etag and remote_etag == _last_etag:
            return False

        connections.close_all()
        tmp_path = db_path.with_suffix(".sqlite3.download")
        with driver.open_file(S3_DB_KEY) as stream, open(tmp_path, "wb") as out:
            while True:
                chunk = stream.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        os.replace(tmp_path, db_path)
        _last_etag = remote_etag
        return True


def sync_sqlite_to_s3() -> None:
    """Flush and persist local SQLite DB back to private S3 bucket."""
    global _last_sync_ts, _last_etag
    if not is_s3_sqlite_sync_enabled():
        return

    with _sync_lock:
        db_path = Path(settings.DATABASES["default"]["NAME"])
        if not db_path.exists():
            return
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        except Exception:
            pass
        connections.close_all()

        driver = _get_s3_driver()
        with open(db_path, "rb") as fh:
            resp = driver.client.put_object(
                Bucket=driver.bucket,
                Key=S3_DB_KEY,
                Body=fh.read(),
                ContentType="application/x-sqlite3",
                ServerSideEncryption="AES256",
            )
        _last_etag = (resp.get("ETag") or "").strip('"')
        _last_sync_ts = time.time()


class S3SqliteSyncMiddleware:
    """Keeps /tmp SQLite consistent across Vercel serverless containers."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_s3_sqlite_sync_enabled() and request.path.startswith("/api/"):
            sync_sqlite_from_s3(force=False)

        response = self.get_response(request)

        if (
            is_s3_sqlite_sync_enabled()
            and request.path.startswith("/api/")
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and 200 <= response.status_code < 300
        ):
            sync_sqlite_to_s3()

        return response
