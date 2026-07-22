from .settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test.sqlite3',
    }
}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
MEDIA_ROOT = BASE_DIR / 'test_media'
AXES_ENABLED = False
MIGRATION_MODULES = {
    'users': None,
    'pets': None,
    'clinics': None,
    'appointments': None,
    'messaging': None,
    'lost_pets': None,
    'contact': None,
    'ads': None,
    'blog': None,
    'community': None,
    'partners': None,
    'adoptions': None,
    'commerce': None,
    'axes': None,
}
CORS_ALLOWED_ORIGINS = ['http://127.0.0.1:5173', 'http://localhost:5173']
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']
