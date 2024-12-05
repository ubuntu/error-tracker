#!/usr/bin/python
from txstatsd.client import UdpStatsDClient
from txstatsd.metrics.metrics import Metrics
from datetime import datetime

import pycassa

from cassandra import ConsistencyLevel
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider

from daisy import config

METRICS = None
def get_metrics(namespace='daisy'):
    global METRICS
    if METRICS is None:
        connection = UdpStatsDClient(host=config.statsd_host,
                                     port=config.statsd_port)
        connection.connect()
        namespace = 'whoopsie-daisy.' + namespace
        METRICS = Metrics(connection=connection, namespace=namespace)
    return METRICS

class VerboseListener(pycassa.pool.PoolListener):
    def connection_checked_in(self, dic):
        print datetime.now(), 'connection_checked_in', dic
    def connection_checked_out(self, dic):
        print datetime.now(), 'connection_checked_out', dic
    def connection_created(self, dic):
        print datetime.now(), 'connection_created', dic
    def connection_disposed(self, dic):
        print datetime.now(), 'connection_disposed', dic
    def connection_failed(self, dic):
        print datetime.now(), 'connection_failed', dic
    def connection_recycled(self, dic):
        print datetime.now(), 'connection_recycled', dic
    def pool_at_max(self, dic):
        print datetime.now(), 'pool_at_max', dic
    def pool_disposed(self, dic):
        print datetime.now(), 'pool_disposed', dic
    def server_list_obtained(self, dic):
        print datetime.now(), 'server_list_obtained', dic

class MeteredListener(pycassa.pool.PoolListener):
    def __init__(self, namespace):
        self.namespace = namespace
    def connection_created(self, dic):
        name = 'cassandra_connection_creations'
        get_metrics(self.namespace).meter(name)
    def connection_disposed(self, dic):
        name = 'cassandra_connection_disposals'
        get_metrics(self.namespace).meter(name)
    def connection_failed(self, dic):
        name = 'cassandra_connection_failures'
        get_metrics(self.namespace).meter(name)
    def pool_at_max(self, dic):
        name = 'cassandra_pool_at_max'
        get_metrics(self.namespace).meter(name)

def wrapped_connection_pool(namespace='daisy'):
    creds = {'username': config.cassandra_username,
             'password': config.cassandra_password}
    pycassa.ConsistencyLevel.LOCAL_QUORUM
    return pycassa.ConnectionPool(config.cassandra_keyspace,
                                  config.cassandra_hosts,
                                  listeners=[MeteredListener(namespace)],
                                  timeout=30,
                                  pool_size=config.cassandra_pool_size,
                                  max_overflow=config.cassandra_max_overflow,
                                  # Pycassa will sleep for 10.24 seconds before
                                  # the last retry.
                                  max_retries=10, credentials=creds)

def cassandra_session():
    auth_provider = PlainTextAuthProvider(
        username=config.cassandra_username, password=config.cassandra_password)
    cluster = Cluster(config.cassandra_hosts, auth_provider=auth_provider)
    cassandra_session = cluster.connect(config.cassandra_keyspace)
    cassandra_session.default_consistency_level = ConsistencyLevel.LOCAL_ONE
    return cassandra_session

def record_revno(namespace='daisy'):
    from daisy.version import version_info
    import socket
    if 'revno' in version_info:
        m = '%s.version.daisy' % socket.gethostname()
        get_metrics(namespace).gauge(m, version_info['revno'])
