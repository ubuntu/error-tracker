#!/usr/bin/python

from cassandra import ConsistencyLevel
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import SimpleStatement

from binascii import hexlify

from daisy import launchpad
from daisy import config

auth_provider = PlainTextAuthProvider(
    username=config.cassandra_username, password=config.cassandra_password)
cluster = Cluster(config.cassandra_hosts, auth_provider=auth_provider)
session = cluster.connect(config.cassandra_keyspace)
session.default_consistency_level = ConsistencyLevel.LOCAL_ONE


def import_user_binary_packages(user):
    binary_packages = launchpad.get_subscribed_packages(user)
    bin_pkgs_tbl = 'UserBinaryPackages'
    hex_empty = '0x' + hexlify('')
    for binary_package in binary_packages:
        # print("%s: %s" % (user, binary_package))
        session.execute(SimpleStatement
            ("INSERT INTO \"%s\" (key, column1, value) VALUES ('%s', '%s', %s)"
             % (bin_pkgs_tbl, user, binary_package, hex_empty)))


if __name__ == '__main__':
    teams = ['ubuntu-x-swat', 'desktop-packages', 'ubuntu-server',
             'foundations-bugs', 'edubuntu-bugs', 'kubuntu-bugs',
             'lubuntu-packaging', 'xubuntu-bugs', 'ubuntu-security', 'laney',
             'kernel-packages']
    for team in teams:
        import_user_binary_packages(team)
