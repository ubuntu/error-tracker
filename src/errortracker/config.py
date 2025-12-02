# Error Tracker settings
import logging
from logging.config import dictConfig

dictConfig({"version": 1, "disable_existing_loggers": False})
logger = logging.getLogger("errortracker")

log_level = logging.INFO

# TODO: convert that to a TOML/YAML/JSON/else real configuration file

amqp_creds = {
    "host": "127.0.0.1:5672",
    "username": "guest",
    "password": "guest",
}

cassandra_creds = {
    "keyspace": "crashdb",
    # The addresses of the Cassandra database nodes.
    "hosts": ["localhost"],
    "username": "",
    "password": "",
    # should be a multiple of cassandra_hosts
    "pool_size": 9,
    # allow the pool to overflow
    "max_overflow": 18,
}
cassandra_consistency_level = "ONE"

# Example:
# swift_creds = {
#     "os_auth_url": "http://keystone.example.com/",
#     "os_username": "ostack",
#     "os_password": "secret",
#     "os_tenant_name": "ostack_project",
#     "os_region_name": "region01",
#     "auth_version": "3.0",
# }
# Default value is good for local dev with saio
swift_creds = {
    "os_auth_url": "http://127.0.0.1:8080/auth/v1.0",
    "os_username": "test:tester",
    "os_password": "testing",
    "auth_version": "1.0",
}

# The swift container to store cores
swift_bucket = "cores"

# Path used to keep some crashes in case of failure, for manual investigation
failure_storage = None

errors_secret_key = "hellotheregeneralkenobi"
openid_trust_root = "openidyouwillsoonbegone"
allow_bug_filing = True
lp_oauth_token = "todofixme"
lp_oauth_secret = "todofixme"
lp_use_staging = True
http_cache_dir = "/tmp/errors/http_cache_dir"

try:
    from local_config import *  # noqa: F403

    logger.info("loaded local settings")
except ImportError:
    logger.info("didn't find local settings")


logger.setLevel(log_level)
