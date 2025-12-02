import inspect
import os

from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import ConsistencyLevel
from cassandra.cqlengine import connection, management
from cassandra.policies import RoundRobinPolicy

import errortracker.cassandra_schema
from errortracker import config

_connected = False
_session = None
KEYSPACE: str = config.cassandra_creds["keyspace"]
REPLICATION_FACTOR: int = 3


def setup_cassandra():
    global _connected
    if config.cassandra_creds["username"]:
        auth_provider = PlainTextAuthProvider(
            username=config.cassandra_creds["username"],
            password=config.cassandra_creds["password"],
        )
    else:
        auth_provider = None
    if _connected is False:
        connection.setup(
            config.cassandra_creds["hosts"],
            KEYSPACE,
            consistency=ConsistencyLevel.name_to_value[config.cassandra_consistency_level],
            auth_provider=auth_provider,
            load_balancing_policy=RoundRobinPolicy(),
            protocol_version=4,
        )
        _connected = True
    sync_schema()
    # workaround some weirdness in keyspace handling
    connection.get_session().keyspace = KEYSPACE


def sync_schema():
    skip_sync = False
    results = connection.get_session().execute(
        f"SELECT * FROM system_schema.keyspaces WHERE keyspace_name='{KEYSPACE}'"
    )
    for row in results:
        skip_sync = True
    if skip_sync:
        config.logger.info("Cassandra keyspace already exists, not syncing schema")
        return
    config.logger.info("Cassandra keyspace does not exists, syncing schema")

    # cassandra wants this environment variable to be set, otherwise issues a
    # warning. Let's please it.
    # This is because there might be issues where multiple processes concurently
    # try to modify the schema, and this is DANGEROUS for Cassandra.
    # TODO: find a way to create the keyspace and sync_schema() only once
    # atomically, even in development.

    os.environ["CQLENG_ALLOW_SCHEMA_MANAGEMENT"] = "1"
    management.create_keyspace_simple(name=KEYSPACE, replication_factor=REPLICATION_FACTOR)

    def _find_subclasses(module, clazz):
        return [
            cls
            for name, cls in inspect.getmembers(module)
            if inspect.isclass(cls) and issubclass(cls, clazz) and cls is not clazz
        ]

    for klass in _find_subclasses(
        errortracker.cassandra_schema, errortracker.cassandra_schema.ErrorTrackerTable
    ):
        management.sync_table(klass)


def cassandra_session():
    global _session
    if not _session:
        _session = connection.get_session()
    return _session
