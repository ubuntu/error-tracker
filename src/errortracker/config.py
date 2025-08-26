# Error Tracker settings


# TODO: convert that to a TOML/YAML/JSON/else real configuration file

# The Cassandra keyspace to use.
cassandra_keyspace = "crashdb"

# The addresses of the Cassandra database nodes.
cassandra_hosts = ["localhost:9042"]

# The username to connect with.
cassandra_username = ""

# The password to use.
cassandra_password = ""

# should be a multiple of cassandra_hosts
cassandra_pool_size = 9

# allow the pool to overflow
cassandra_max_overflow = 18


try:
    from local_settings import *  # noqa: F403

    print("Loaded local settings")
except ImportError:
    print("Didn't find local settings")
