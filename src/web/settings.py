# Django settings for errors project.
import os
from daisy import config

ALLOWED_HOSTS = config.allowed_hosts

DATABASES = config.django_databases

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

DEBUG = False

ADMINS = (
)

MANAGERS = ADMINS

# Full import path of a serializer class to use for serializing session data.
# Global default for this switched to JSONSerializer with Django 1.6
# c.f.
# https://stackoverflow.com/questions/24229397/django-object-is-not-json-serializable-error-after-upgrading-django-to-1-6-5
SESSION_SERIALIZER = 'django.contrib.sessions.serializers.PickleSerializer'

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = False

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = False

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = '%s' % os.path.join(PROJECT_ROOT, '../static')

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = config.errors_static_url

# URL prefix for admin static files -- CSS, JavaScript and images.
# Make sure to use a trailing slash.
# Examples: "http://foo.com/static/admin/", "/static/admin/".
ADMIN_MEDIA_PREFIX = '/static/admin/'

# Additional locations of static files
STATICFILES_DIRS = [
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(PROJECT_ROOT, 'static'),
]

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
]

# Make this unique, and don't share it with anybody.
SECRET_KEY = config.errors_secret_key

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

AUTHENTICATION_BACKENDS = (
        'django_openid_auth.auth.OpenIDBackend',
        'django.contrib.auth.backends.ModelBackend',
)

ROOT_URLCONF = 'errors.urls'

#TEMPLATE_DIRS = (
#    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
#    # Always use forward slashes, even on Windows.
#    # Don't forget to use absolute paths, not relative paths.
#    os.path.join(PROJECT_ROOT, 'templates'),
#)

TEMPLATES = [
   {
       'BACKEND': 'django.template.backends.django.DjangoTemplates',
       'DIRS': [os.path.join(PROJECT_ROOT, 'templates')],
       'OPTIONS': {
           'context_processors': [
               'django.template.context_processors.request',
               'django.template.context_processors.static',
               'errors.context_processors.login_url_with_redirect',
           ],
           'loaders': [
               'django.template.loaders.filesystem.Loader',
               'django.template.loaders.app_directories.Loader',
               # 'django.template.loaders.eggs.Loader',
           ],
       },
   }
]

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Uncomment the next line to enable the admin:
    # 'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',
    'errors',
    'django_openid_auth',
)

# Force HTTPS when the X-Forwarded-Proto header is set to https
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

OPENID_CREATE_USERS = True
OPENID_UPDATE_DETAILS_FROM_SREG = True
OPENID_USE_EMAIL_FOR_USERNAME = True
OPENID_STRICT_USERNAMES = True
OPENID_FOLLOW_RENAMES = True
LOGIN_URL = '/openid/login/'
LOGIN_REDIRECT_URL = '/'
OPENID_SSO_SERVER_URL = 'https://login.ubuntu.com/'
OPENID_TRUST_ROOT = config.openid_trust_root
OPENID_LAUNCHPAD_TEAMS_MAPPING = {
    'daisy-pluckers': 'daisy-pluckers',
    'canonical-ubuntu-platform': 'canonical-ubuntu-platform',
    'canonical-losas': 'canonical-losas',
    'canonical-product-strategy': 'canonical-product-strategy',
    'canonical-hw-cert': 'canonical-hw-cert',
    'canonical-hwe-team': 'canonical-hwe-team',
    'online-accounts': 'online-accounts',
    'error-tracker-access': 'error-tracker-access',
}
OPENID_SREG_REQUIRED_FIELDS = ['nickname']
# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
}

if config.allow_bug_filing == 'True':
    ALLOW_BUG_FILING = 1
else:
    ALLOW_BUG_FILING = 0
