"""
Django settings for the TEL Education Link Student Portal.

Configuration is entirely environment driven. Copy ``.env.example`` to ``.env``
and fill in the values before running the project.

Design rules encoded here:
  * PostgreSQL is the production database. ``DATABASE_URL`` (or the discrete
    ``POSTGRES_*`` variables) selects it. When no PostgreSQL configuration is
    present the project falls back to a local SQLite file so that a clean clone
    can be run with a single command in development.
  * Authentication is JWT based and the tokens are delivered as ``HttpOnly``
    cookies, never from JavaScript. Unsafe requests additionally require a
    double-submit CSRF token.
  * Uploads are validated (extension + declared MIME + size) and are never
    served from arbitrary filesystem paths.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env(key: str, default: str | None = None) -> str | None:
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    return value


def env_bool(key: str, default: bool = False) -> bool:
    raw = env(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(key: str, default: str = "") -> list[str]:
    raw = env(key, default) or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = env("SECRET_KEY", "insecure-development-key-do-not-use-in-production")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# True in production, false for the local HTTP dev server.
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", False)
SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "0") or 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "corsheaders",
    "common",
    "accounts",
    "academics",
    "assessment",
    "engagement",
    "core",
    "integration",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.RequestContextMiddleware",
    "core.middleware.ApiRateLimitMiddleware",
]

ROOT_URLCONF = "telportal.urls"

TEMPLATES = [
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
    },
]

WSGI_APPLICATION = "telportal.wsgi.application"
ASGI_APPLICATION = "telportal.asgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


def _database_from_url(url: str) -> dict:
    parsed = urlparse(url)
    engines = {
        "postgres": "django.db.backends.postgresql",
        "postgresql": "django.db.backends.postgresql",
        "psql": "django.db.backends.postgresql",
        "sqlite": "django.db.backends.sqlite3",
    }
    engine = engines.get(parsed.scheme)
    if engine is None:
        raise ValueError(f"Unsupported DATABASE_URL scheme: {parsed.scheme!r}")

    if engine.endswith("sqlite3"):
        name = unquote(parsed.path or "").lstrip("/") or ":memory:"
        if name != ":memory:":
            name = str(BASE_DIR / name)
        return {"ENGINE": engine, "NAME": name, "CONN_MAX_AGE": 0}

    query = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
    options: dict = {
        "ENGINE": engine,
        "NAME": unquote(parsed.path or "").lstrip("/"),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "CONN_MAX_AGE": int(query.get("conn_max_age", 60)),
    }
    if query.get("sslmode"):
        options["OPTIONS"] = {"sslmode": query["sslmode"]}
    return options


_database_url = env("DATABASE_URL")
if _database_url:
    DATABASES = {"default": _database_from_url(_database_url)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "telportal.sqlite3"),
        }
    }

DATABASES["default"]["ATOMIC_REQUESTS"] = False
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

# ---------------------------------------------------------------------------
# Internationalisation / time
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", "Asia/Karachi")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media
# ---------------------------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))
MEDIA_URL = env("MEDIA_URL", "/media/")

# Production file storage: switch to an S3 compatible backend by setting
# TEL_STORAGE_BACKEND=s3 together with the TEL_S3_* variables.
TEL_STORAGE_BACKEND = env("TEL_STORAGE_BACKEND", "local")
if TEL_STORAGE_BACKEND == "s3":
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env("TEL_S3_BUCKET", ""),
            "access_key": env("TEL_S3_ACCESS_KEY", ""),
            "secret_key": env("TEL_S3_SECRET_KEY", ""),
            "endpoint_url": env("TEL_S3_ENDPOINT_URL") or None,
            "region_name": env("TEL_S3_REGION", ""),
            "default_acl": "private",
            "querystring_auth": True,
            "file_overwrite": False,
        },
    }

# Upload policy — enforced in `common.uploads`.
MAX_UPLOAD_BYTES = int(env("MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))
ALLOWED_UPLOAD_EXTENSIONS = env_list(
    "ALLOWED_UPLOAD_EXTENSIONS",
    "pdf,png,jpg,jpeg,webp,doc,docx,txt,csv,xls,xlsx",
)
# Uploads are private: they are streamed through an authorised view.
UPLOAD_SERVING_VIEW = env_bool("UPLOAD_SERVING_VIEW", True)

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.CookieJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.TelPagination",
    "PAGE_SIZE": 12,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "common.exceptions.tel_exception_handler",
    "DATETIME_FORMAT": "iso-8601",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_ACCESS_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": env("JWT_SIGNING_KEY") or SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_TYPE_CLAIM": "token_type",
}

ACCESS_COOKIE_NAME = env("ACCESS_COOKIE_NAME", "tel_at")
REFRESH_COOKIE_NAME = env("REFRESH_COOKIE_NAME", "tel_rt")
CSRF_COOKIE_NAME = "tel_csrftoken"
CSRF_HEADER_NAME = "HTTP_X_TEL_CSRFTOKEN"
CSRF_COOKIE_HTTPONLY = False  # readable by the SPA to echo back in a header
SESSION_COOKIE_NAME = "tel_sessionid"
SESSION_COOKIE_HTTPONLY = True

LOGIN_THROTTLE_RATE = env("LOGIN_THROTTLE_RATE", "10/min")
LOGIN_THROTTLE_BURST = int(env("LOGIN_THROTTLE_BURST", "5"))

# ---------------------------------------------------------------------------
# CORS — the SPA is a separate origin in development
# ---------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-language",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-tel-csrftoken",
    "x-requested-with",
]
CORS_EXPOSE_HEADERS = ["X-Tel-Trace"]
CSRF_COOKIE_NAME = CSRF_COOKIE_NAME

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

TEL_RATE_LIMITS = {
    "api": env("RATE_LIMIT_API", "1200/min"),
    "session": env("RATE_LIMIT_SESSION", "600/min"),
    "auth": env("RATE_LIMIT_AUTH", "30/min"),
    "write": env("RATE_LIMIT_WRITE", "240/min"),
    "upload": env("RATE_LIMIT_UPLOAD", "40/min"),
}
RATE_LIMIT_ENABLED = env_bool("RATE_LIMIT_ENABLED", True)

# ---------------------------------------------------------------------------
# TEL core integration
# ---------------------------------------------------------------------------

TEL_INTEGRATION_ADAPTER = env("TEL_INTEGRATION_ADAPTER", "local")
TEL_CORE_API_BASE_URL = env("TEL_CORE_API_BASE_URL", "")
TEL_CORE_API_KEY = env("TEL_CORE_API_KEY", "")
TEL_CORE_API_TIMEOUT = float(env("TEL_CORE_API_TIMEOUT", "15"))
TEL_SYNC_ENABLED = env_bool("TEL_SYNC_ENABLED", False)
TEL_SYNC_INTERVAL_MINUTES = int(env("TEL_SYNC_INTERVAL_MINUTES", "60"))

# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

TEL_CACHE_TTL_DASHBOARD = int(env("TEL_CACHE_TTL_DASHBOARD", "60"))
TEL_CACHE_TTL_LOOKUPS = int(env("TEL_CACHE_TTL_LOOKUPS", "600"))
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "telportal",
        "TIMEOUT": TEL_CACHE_TTL_LOOKUPS,
    }
}

# ---------------------------------------------------------------------------
# Email (password reset)
# ---------------------------------------------------------------------------

EMAIL_BACKEND = env(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@tel.edu.pk")
PASSWORD_RESET_TTL_MINUTES = int(env("PASSWORD_RESET_TTL_MINUTES", "30"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)-8s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "telportal.audit": {"level": "INFO", "handlers": ["console"], "propagate": False},
    },
}

# ---------------------------------------------------------------------------
# Product configuration
# ---------------------------------------------------------------------------

# Weak-subject detection thresholds (configurable, used by the analytics engine).
TEL_WEAK_SUBJECT_SCORE = float(env("TEL_WEAK_SUBJECT_SCORE", "65"))
TEL_WEAK_SUBJECT_MIN_ATTEMPTS = int(env("TEL_WEAK_SUBJECT_MIN_ATTEMPTS", "2"))
TEL_ATTENDANCE_TARGET = float(env("TEL_ATTENDANCE_TARGET", "75"))

FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_BYTES
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_BYTES + 1024 * 1024

APPEND_SLASH = True
