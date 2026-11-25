"""WSGI config for cloudbox project."""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cloudbox.settings")
application = get_wsgi_application()
