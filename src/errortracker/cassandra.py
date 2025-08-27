from cassandra import ConsistencyLevel
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster

from errortracker import config

_session = None


def create_cassandra_session():
    auth_provider = PlainTextAuthProvider(
        username=config.cassandra_username, password=config.cassandra_password
    )
    print("connecting to " + str(config.cassandra_hosts))
    cluster = Cluster(config.cassandra_hosts, auth_provider=auth_provider)
    cassandra_session = cluster.connect()
    cassandra_session.execute(
        "CREATE KEYSPACE IF NOT EXISTS crashdb WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1 };"
    )
    cassandra_session = cluster.connect(config.cassandra_keyspace)
    cassandra_session.default_consistency_level = ConsistencyLevel.LOCAL_ONE
    return cassandra_session


def cassandra_session():
    global _session
    if not _session:
        _session = create_cassandra_session()
    return _session
