import os
import sys
import threading
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cloudbox.settings")

from django.conf import settings  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.core.wsgi import get_wsgi_application  # noqa: E402

from cloudbox.db_sync import (  # noqa: E402
    is_s3_sqlite_sync_enabled,
    sync_sqlite_from_s3,
    sync_sqlite_to_s3,
)

_init_lock = threading.Lock()
_initialized = False


def _ensure_initialized():
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        settings.WRITABLE_TMP_DIR.mkdir(parents=True, exist_ok=True)
        using_sqlite = (
            not settings.DATABASE_URL
            and os.environ.get("DB_ENGINE", "sqlite").lower() != "mysql"
        )
        if os.environ.get("VERCEL") and using_sqlite:
            downloaded = False
            if is_s3_sqlite_sync_enabled():
                downloaded = sync_sqlite_from_s3(force=True)
            db_file = Path(settings.DATABASES["default"]["NAME"])
            marker = settings.WRITABLE_TMP_DIR / ".migrated"
            if not downloaded or not db_file.exists():
                call_command("migrate", interactive=False, verbosity=0)
                if os.environ.get("AUTO_SEED_DEMO", "true").lower() == "true":
                    call_command("seed_demo", verbosity=0)
                if is_s3_sqlite_sync_enabled():
                    sync_sqlite_to_s3()
            elif not marker.exists():
                call_command("migrate", interactive=False, verbosity=0)
            marker.touch()
        _initialized = True


_wsgi_app = get_wsgi_application()


def app(environ, start_response):
    _ensure_initialized()
    return _wsgi_app(environ, start_response)
