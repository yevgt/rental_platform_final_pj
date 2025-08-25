import os
from datetime import timedelta
from pathlib import Path
import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    MYSQL=(bool, False),
)

# .env
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# SECRET_KEY = 'django-insecure-jp4_9abi&1e!v)$u1erkc44y5l6b)!&3)q7gf+7$@hpr4qll31'
SECRET_KEY = env("SECRET_KEY")


# SECURITY WARNING: don't run with debug turned on in production!
# DEBUG = True
DEBUG = env("DEBUG")

# ALLOWED_HOSTS = []
ALLOWED_HOSTS = [h.strip() for h in env("ALLOWED_HOSTS", default="127.0.0.1,localhost").split(",")]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "drf_spectacular",
    "rest_framework_simplejwt.token_blacklist",


    # Local apps
    "accounts",
    "properties",
    "bookings.apps.BookingsConfig",
    "reviews.apps.ReviewsConfig",
    "analytics",
    "notifications",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "rental_platform.middleware.RequestLogMiddleware",
]

ROOT_URLCONF = 'rental_platform.urls'

# TEMPLATES = [
#     {
#         'BACKEND': 'django.template.backends.django.DjangoTemplates',
#         'DIRS': [BASE_DIR / 'templates']
#         ,
#         'APP_DIRS': True,
#         'OPTIONS': {
#             'context_processors': [
#                 'django.template.context_processors.request',
#                 'django.contrib.auth.context_processors.auth',
#                 'django.contrib.messages.context_processors.messages',
#             ],
#         },
#     },
# ]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # for custom DRF templates (if required)
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

WSGI_APPLICATION = 'rental_platform.wsgi.application'
ASGI_APPLICATION = "rental_platform.asgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

USE_MYSQL = env("MYSQL")

if USE_MYSQL:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env("MYSQL_NAME"),
            "USER": env("MYSQL_USER"),
            "PASSWORD": env("MYSQL_PASSWORD"),
            "HOST": env("MYSQL_HOST", default="localhost"),
            "PORT": env("MYSQL_PORT", default="3306"),
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Europe/Berlin'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",  # for working with access/refresh tokens
        "rest_framework.authentication.SessionAuthentication",        # to work with sessions (usually a browser)
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",  # any user (even unauthorized) can make requests to the API by default
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",  # for autogeneration of OpenAPI schema (Swagger).
}

SIMPLE_JWT = {
    # For compatibility with blacklisting all active refresh tokens when deleting an account
    'ROTATE_REFRESH_TOKENS': True,
    "BLACKLIST_AFTER_ROTATION": True,
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),  # For example, 60 minutes instead of the standard 5
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),     # For example, 7 days
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Rental Platform API",
    "DESCRIPTION": "API for housing rental system (ads, bookings, reviews, analytics).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SECURITY": [{"BearerAuth": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
}

# Directory for logs
LOG_DIR = BASE_DIR / "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "simple": {
            "format": "[{levelname}] {asctime} {name}: {message}",
            "style": "{",
        },
        "verbose": {
            "format": "{asctime} | {levelname} | {name} | pid={process} tid={thread} | {message}",
            "style": "{",
        },
        # If desired, you can add a JSON formatter (you will need the python-json-logger package)
        # "json": {
        #     "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
        #     "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
        # },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "simple",
        },
        "app_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "filename": str(LOG_DIR / "app.log"),
            "maxBytes": 5 * 1024 * 1024,  # 5 MB
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "verbose",
        },
        "requests_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "filename": str(LOG_DIR / "requests.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "verbose",
        },
        "security_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "WARNING",
            "filename": str(LOG_DIR / "security.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "verbose",
        },
    },

    # root logger for the project
    "root": {
        "handlers": ["console", "app_file"],
        "level": "INFO",
    },

    "loggers": {
        # Requests/Responses (uses middleware below)
        "requests": {
            "handlers": ["console", "requests_file"],
            "level": "INFO",
            "propagate": True,
        },
        # Django queries with errors (4xx-5xx)
        "django.request": {
            "handlers": ["console", "requests_file"],
            "level": "WARNING",
            "propagate": False,
        },
        # Safety
        "django.security": {
            "handlers": ["console", "security_file"],
            "level": "WARNING",
            "propagate": False,
        },
        # Example: More detailed logs in your applications
        "accounts": {"level": "INFO"},
        "properties": {"level": "INFO"},
        "bookings": {"level": "INFO"},
        "reviews": {"level": "INFO"},
        "analytics": {"level": "INFO"},
        "notifications": {"level": "INFO"},
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

LOGIN_REDIRECT_URL = "/api/accounts/me/"
LOGOUT_REDIRECT_URL = "/api/accounts/me/"
