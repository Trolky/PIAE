"""Django settings for the PIAE frontend.

This Django app acts as a server-rendered UI that communicates with the FastAPI
backend using a small HTTP client.

Configuration is mostly driven by environment variables:
- BACKEND_API_BASE_URL

Notes:
    Django uses cookie-based sessions (SQLite by default) to store a JWT token.
"""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY: str = "dev-secret-key-change-me"
DEBUG: bool = True
ALLOWED_HOSTS: list[str] = ["*"]

import os
BACKEND_API_BASE_URL: str = os.environ.get("BACKEND_API_BASE_URL", "http://localhost:8000")

SESSION_JWT_KEY: str = "access_token"
SESSION_USER_KEY: str = "user"

INSTALLED_APPS: list[str] = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "web",
]

MIDDLEWARE: list[str] = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF: str = "frontend.urls"

TEMPLATES: list[dict[str, str | list[Path] | bool | dict[str, list[str]]]] = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION: str = "frontend.wsgi.application"
ASGI_APPLICATION: str = "frontend.asgi.application"

DATABASES: dict[str, dict[str, str | Path]] = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS: list[dict[str, str]] = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE: str = "en"

LANGUAGES: list[tuple[str, str]] = [
    ("en", "English"),
    ("cs", "Čeština"),
]

LOCALE_PATHS: list[Path] = [BASE_DIR / "locale"]

TIME_ZONE: str = "UTC"
USE_I18N: bool = True
USE_L10N: bool = True
USE_TZ: bool = True

STATIC_URL: str = "static/"
STATICFILES_DIRS: list[Path] = [BASE_DIR / "static"]

SESSION_COOKIE_HTTPONLY: bool = True

DEFAULT_AUTO_FIELD: str = "django.db.models.BigAutoField"
