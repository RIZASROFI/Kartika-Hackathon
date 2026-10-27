"""Konfigurasi Django untuk KARTIKA Intel."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

for env_file in (BASE_DIR / ".env", PROJECT_ROOT / ".env"):
    if env_file.is_file():
        load_dotenv(env_file)


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def database_from_url(raw_url: str) -> dict:
    """Dukung SQLite dan PostgreSQL lewat satu DATABASE_URL."""
    parsed = urlparse(raw_url)
    if parsed.scheme == "sqlite":
        path = unquote(parsed.path)
        name = path.lstrip("/")
        if name.startswith("./"):
            name = name[2:]
        if name in {"", ":memory:"}:
            name = ":memory:"
        else:
            candidate = Path(name)
            if not candidate.is_absolute():
                candidate = BASE_DIR / candidate
            name = str(candidate)
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": name}

    if parsed.scheme in {"postgres", "postgresql"}:
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed.path.lstrip("/")),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
        }

    raise ValueError(
        f"DATABASE_URL tidak didukung: {parsed.scheme}. Gunakan sqlite:/// atau postgresql://"
    )


APP_NAME = os.getenv("APP_NAME", "KARTIKA Intel")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "127.0.0.1,localhost")

INSTALLED_APPS = [
    # Didaftarkan lebih dulu agar management command runserver kustom menang
    # atas versi django.contrib.staticfiles (tetap mewarisi perilakunya).
    "intel",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "satria.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "satria.wsgi.application"
ASGI_APPLICATION = "satria.asgi.application"

DATABASES = {
    "default": database_from_url(os.getenv("DATABASE_URL", "sqlite:///./kartika_intel.db"))
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "id"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        *(["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else []),
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "EXCEPTION_HANDLER": "intel.api.exceptions.api_exception_handler",
}

# Lokasi hasil build React. Django menyajikan SPA agar `manage.py runserver`
# cukup satu perintah pada demo.
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

FETCH_TIMEOUT_SECONDS = env_float("FETCH_TIMEOUT_SECONDS", 15.0)
MAX_CONTENT_CHARS = env_int("MAX_CONTENT_CHARS", 60_000)

COORDINATION_SIMILARITY_THRESHOLD = env_float("COORDINATION_SIMILARITY_THRESHOLD", 0.28)
COORDINATION_WINDOW_HOURS = env_int("COORDINATION_WINDOW_HOURS", 72)
COORDINATION_MIN_CORPUS = env_int("COORDINATION_MIN_CORPUS", 3)

# --- Pemeriksaan fakta eksternal (Google Fact Check Tools API) ---
# Nonaktif otomatis saat pengujian agar suite tidak memanggil jaringan.
RUNNING_TESTS = "test" in sys.argv or "pytest" in sys.modules
GOOGLE_FACTCHECK_API_KEY = os.getenv("GOOGLE_FACTCHECK_API_KEY", "").strip()
FACTCHECK_ENABLED = (
    env_bool("FACTCHECK_ENABLED", True)
    and bool(GOOGLE_FACTCHECK_API_KEY)
    and not RUNNING_TESTS
)
FACTCHECK_TIMEOUT_SECONDS = env_float("FACTCHECK_TIMEOUT_SECONDS", 6.0)
FACTCHECK_MAX_QUERIES = env_int("FACTCHECK_MAX_QUERIES", 2)
FACTCHECK_PAGE_SIZE = env_int("FACTCHECK_PAGE_SIZE", 5)
FACTCHECK_CACHE_TTL_HOURS = env_int("FACTCHECK_CACHE_TTL_HOURS", 168)
FACTCHECK_MIN_OVERLAP = env_float("FACTCHECK_MIN_OVERLAP", 0.45)
FACTCHECK_LANGUAGE_CODE = os.getenv("FACTCHECK_LANGUAGE_CODE", "").strip()

LLM_ENABLED = env_bool("LLM_ENABLED", False)
LLM_API_KEY = os.getenv("LLM_API_KEY") or None
LLM_MODEL = os.getenv("LLM_MODEL") or None

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "satria.logging.JsonFormatter"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django.server": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "httpx": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
