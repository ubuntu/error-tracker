# Copyright © 2011-2013 Canonical Ltd.
# Author: Evan Dandrea <evan.dandrea@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero Public License as published by
# the Free Software Foundation; version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero Public License for more details.
#
# You should have received a copy of the GNU Affero Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# The Cassandra keyspace to use.
cassandra_keyspace = "crashdb"

# The addresses of the Cassandra database nodes.
# cassandra_hosts = ['192.168.10.2:9160']
cassandra_hosts = ["192.168.10.2:9042"]

# The username to connect with.
cassandra_username = ""

# The password to use.
cassandra_password = ""

# should be a multiple of cassandra_hosts
cassandra_pool_size = 9

# allow the pool to overflow
cassandra_max_overflow = 18

# list of strings representing the host/domain names that will be served
allowed_hosts = ["127.0.0.1", "localhost"]

# The AMQP host to receive messages from.
amqp_host = "127.0.0.1"

# The AMQP username.
amqp_username = ""

# The AMQP username.
amqp_password = ""

# The AMQP host to receive messages from for OOPS reports.
oops_amqp_host = "127.0.0.1"

# The AMQP username for OOPS reports.
oops_amqp_username = ""

# The AMQP username for OOPS reports.
oops_amqp_password = ""

# The AMQP exchange name for OOPS reports.
oops_amqp_exchange = ""

# The AMQP virtual host for OOPS reports.
oops_amqp_vhost = ""

# The AMQP routing key (queue) for OOPS reports.
oops_amqp_routing_key = "oopses"

# The path to the SAN for storing core dumps (deprecated).
san_path = "/srv/cores"

# The path to store OOPS reports in for http://errors.ubuntu.com.
oops_repository = "/srv/local-oopses-whoopsie"

# The host and port of the txstatsd server.
statsd_host = "localhost"

statsd_port = 8125

# Use Launchpad staging instead of production.
lp_use_staging = False

# Launchpad OAuth tokens.
# See https://wiki.ubuntu.com/ErrorTracker/Contributing/Errors
lp_oauth_token = ""
lp_oauth_secret = ""

# Directory for httplib2's request cache.
http_cache_dir = "/tmp/errors.ubuntu.com-httplib2-cache"

# Database configuration for the Errors Django application. This database is
# used to store OpenID login information.
django_databases = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": "django_db",
        "USER": "django_login",
        "PASSWORD": "",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

# S3 configuration (deprecated). Only set these if you're using S3 for storing
# the core files.
aws_access_key = ""
aws_secret_key = ""
ec2_host = ""

# The bucket to place core files in when using S3 (deprecated).
ec2_bucket = ""

# Swift configuration (deprecated). Only set these if you're using Swift for
# storing the core files.
os_auth_url = ""
os_username = ""
os_password = ""
os_tenant_name = ""
os_region_name = ""

# The bucket to place core files in when using Swift (deprecated).
swift_bucket = ""

# The core_storage parameter lists the available providers for saving the
# uploaded core files until they're retraced.
#
# If no storage_write_weights are provided below, it is assumed that the
# 'default' member should receive all the core files. It is an error to not
# provide a default or storage_write_weights, but you can omit a default if
# storage_write_weights is set.
#
# Example:
# core_storage = {
#     'default': 'swift-storage',
#     'local-s1': {'type': 'local',
#                'path': '/srv/cores'}
#     'swift-storage': {'type': 'swift',
#                       'bucket': 'cores',
#                       'os_auth_url': 'http://keystone.example.com/',
#                       'os_username': 'ostack',
#                       'os_password': 'secret',
#                       'os_tenant_name': 'ostack_project',
#                       'os_region_name': 'region01'}
#     's3-east-1': {'type': 's3',
#                   'bucket': 'cores',
#                   'host': 's3.amazonaws.com',
#                   'aws_secret_key': 'secret',
#                   'aws_access_key': 'access-key'}
# }

core_storage = {}

# The storage_write_weights parameter specifies the rough percentage of
# incoming reports that should go to each provider (0.0, 1.0]. You do not have
# to specify percentages for all providers. Any provider without a percentage
# will not be used. All the percentages must total up to 1.0.
#
# Example:
# storage_write_weights = {'local-s1': 0.25, 'swift-storage': 0.75}

storage_write_weights = {}

# The domain name for the Errors service.
openid_trust_root = "https://errors.ubuntu.com/"

# The base URL for static content for https://errors.ubuntu.com
errors_static_url = "https://assets.ubuntu.com/sites/errors/398/"

# Configuration for OOPS reports.
oops_config = {
    "publishers": [
        {
            "type": "amqp",
            "host": oops_amqp_host,
            "user": oops_amqp_username,
            "password": oops_amqp_password,
            "vhost": oops_amqp_vhost,
            "exchange_name": oops_amqp_exchange,
            "routing_key": oops_amqp_routing_key,
        },
        {
            "type": "datedir",
            "error_dir": oops_repository,
            "new_only": True,
        },
    ],
}

# The upper bound for the time it takes from receiving a core to processing it.
# Beyond this point, we'll start alerting.

time_to_retrace_alert = 86400  # 1 day in seconds


# Secret key for errors.ubuntu.com
errors_secret_key = ""

# Hooks for relations in charms to contribute their configuration settings.
try:
    from db_settings import *
except ImportError:
    pass

try:
    from amqp_settings import *
except ImportError:
    pass

try:
    from postgres_settings import *
except ImportError:
    pass

try:
    from local_settings import *
except ImportError:
    pass

allow_bug_filing = "True"
