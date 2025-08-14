from cassandra import ConsistencyLevel
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider

from daisy import config

METRICS = None


class Metrics:
    """
    No-opPrintingMetrics class making the rest of the code to work before moving
    that to some more modern tech.
    """

    def __init__(self, namespace):
        self.namespace = namespace

    def meter(self, *args, **kwargs):
        print(f"meter: {self.namespace}: {args=} | {kwargs=}")

    def gauge(self, *args, **kwargs):
        print(f"gauge: {self.namespace}: {args=} | {kwargs=}")

    def timing(self, *args, **kwargs):
        print(f"timing: {self.namespace}: {args=} | {kwargs=}")


def get_metrics(namespace="daisy"):
    global METRICS
    if METRICS is None:
        namespace = "whoopsie-daisy." + namespace
        METRICS = Metrics(namespace=namespace)
    return METRICS


def cassandra_session():
    auth_provider = PlainTextAuthProvider(
        username=config.cassandra_username, password=config.cassandra_password
    )
    cluster = Cluster(config.cassandra_hosts, auth_provider=auth_provider)
    cassandra_session = cluster.connect(config.cassandra_keyspace)
    cassandra_session.default_consistency_level = ConsistencyLevel.LOCAL_ONE
    return cassandra_session


def record_revno(namespace="daisy"):
    from daisy.version import version_info
    import socket

    if "revno" in version_info:
        m = "%s.version.daisy" % socket.gethostname()
        get_metrics(namespace).gauge(m, version_info["revno"])
