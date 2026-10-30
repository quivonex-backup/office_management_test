from pathlib import Path
from datetime import timedelta
import os
from dotenv import load_dotenv
from decouple import config
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


SECRET_KEY = 'django-insecure-x_6_st^-9dnc!m0^r+8wpn&ps3jhsb5sa4p1g((+h(h&mx55-g'
DEBUG = True
ALLOWED_HOSTS = ['*']


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'django_celery_beat',
    'corsheaders',
    'rest_framework',
    'storages',

    'app.accounts',
    'app.audit',
    'app.clients',
    'app.projects',
    'app.employees',
    'app.location_master',
    'app.payments',
    'app.vendors',
    'app.expenses',
    'app.social_media',
    'app.attendance',
    'app.calendar_app',
    'app.leave'
]

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    "corsheaders.middleware.CorsMiddleware",
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Cors
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers) + ["Authorization"]
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": config("DB_PORT", default="3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {   'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    {   'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',   },
    {   'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',  },
    {   'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Abstract user
AUTH_USER_MODEL = 'accounts.User'


# Your existing REST_FRAMEWORK settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

# Configure token lifetimes here
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),      # Adjust as needed (e.g., hours=12, minutes=30)
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),     # Time limit to get a new access token
    'ROTATE_REFRESH_TOKENS': True,                   # Optional: issue a new refresh token on refresh
    'BLACKLIST_AFTER_ROTATION': True,                # Optional: invalidate old refresh tokens
}


# AWS S3 CONFIGURATION
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default=None)
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default=None)
AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="ap-south-1")
AWS_DEFAULT_ACL = None
AWS_S3_FILE_OVERWRITE = False
AWS_QUERYSTRING_AUTH = False

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


# EMAIL / SMTP CONFIGURATION
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=465, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=True, cast=bool)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=False, cast=bool)
EMAIL_TIMEOUT = 30


FRONTEND_URL = os.getenv("FRONTEND_URL")


MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# COMPANY INFORMATION
COMPANY_NAME = "Quivonex Solutions"
COMPANY_ADDRESS = "Your Company Address"
COMPANY_EMAIL = "your-email@example.com"
COMPANY_PHONE = "+91 9876543210"
COMPANY_GST = "YOUR-GST-NUMBER"


# SOCIAL MEDIA ACCOUNT CONNECT
META_APP_ID = os.getenv("META_APP_ID")
META_APP_SECRET = os.getenv("META_APP_SECRET")
META_CONFIG_ID = os.getenv("META_CONFIG_ID")
META_REDIRECT_URI = os.getenv("META_REDIRECT_URI")
META_API_VERSION = os.getenv("META_API_VERSION")


# CELERY / REDIS
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_BEAT_SCHEDULE = {
    "attendance-auto-mark-absent-every-5-minutes": {
        "task": "app.attendance.tasks.auto_mark_absent_task",
        "schedule": 300.0,
    },
    "attendance-flag-stale-sessions-every-5-minutes": {
        "task": "app.attendance.tasks.flag_stale_attendance_task",
        "schedule": 300.0,
    },
}

