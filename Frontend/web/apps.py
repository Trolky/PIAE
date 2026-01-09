from __future__ import annotations

from django.apps import AppConfig


class WebConfig(AppConfig):
    """Django app configuration for the 'web' UI app."""

    default_auto_field: str = "django.db.models.BigAutoField"
    name: str = "web"
