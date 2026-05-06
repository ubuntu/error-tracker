"""
WSGI config for errors project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

try:
    from uwsgidecorators import postfork

    from errortracker import cassandra

    @postfork
    def connect():
        print("wsgi.py: connecting to Cassandra")
        cassandra.setup_cassandra()
except ImportError:
    print(
        "wsgi.py: Import of 'uwsgidecorators' failed, you might encounter weird hanging of Cassandra-related functions"
    )
    print(
        "wsgi.py: see https://python-driver.readthedocs.io/en/stable/faq.html#why-do-connections-or-io-operations-timeout-in-my-wsgi-application"
    )

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "errors.settings")

application = get_wsgi_application()
