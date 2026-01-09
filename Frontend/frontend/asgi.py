from __future__ import annotations

import os

from django.core.asgi import get_asgi_application
from django.core.handlers.asgi import ASGIHandler

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "frontend.settings")

application: ASGIHandler = get_asgi_application()

