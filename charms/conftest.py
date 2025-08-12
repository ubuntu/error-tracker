import configparser
import logging
from pathlib import Path

import jubilant
import pytest

logger = logging.getLogger()


def charm_path(name: str) -> Path:
    """Return full absolute path to given test charm."""
    charm_dir = Path(__file__).parent / name
    charms = [p.absolute() for p in charm_dir.glob(f"error-tracker-{name}_*.charm")]
    assert charms, f"error-tracker-{name}_*.charm not found"
    assert len(charms) == 1, "more than one .charm file, unsure which to use"
    return charms[0]


@pytest.fixture(scope="module")
def juju() -> jubilant.Juju:
    with jubilant.temp_model() as juju:
        yield juju


@pytest.fixture
def cassandra(juju: jubilant.Juju) -> dict[str, str]:
    juju.deploy(
        "cassandra",
        config={
            "install_keys": "7464AAD9068241C50BA6A26232F35CB2F546D93E",
            "install_sources": "deb https://debian.cassandra.apache.org 311x main",
        },
    )
    juju.wait(
        lambda status: jubilant.all_active(status, "cassandra"),
        timeout=600,
    )
    # Create basic schema
    task = juju.exec(
        "cqlsh",
        "-e",
        "CREATE KEYSPACE IF NOT EXISTS crashdb WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1 };",
        unit="cassandra/0",
    )

    task = juju.exec(
        "cqlsh",
        "-e",
        'CREATE TABLE IF NOT EXISTS crashdb."OOPS" ( key blob, column1 text, value text, PRIMARY KEY (key, column1) );',
        unit="cassandra/0",
    )

    # Get Cassandra credentials
    task = juju.exec("cat", "/home/ubuntu/.cassandra/cqlshrc", unit="cassandra/0")
    logger.info("Cassandra config: " + task.stdout)
    cassandra_creds = configparser.ConfigParser()
    cassandra_creds.read_string(task.stdout)
    return {
        "host": cassandra_creds["connection"]["hostname"],
        "username": cassandra_creds["authentication"]["username"],
        "password": cassandra_creds["authentication"]["password"],
    }


@pytest.fixture
def amqp(juju: jubilant.Juju) -> dict[str, str]:
    juju.deploy("rabbitmq-server")
    juju.wait(
        lambda status: jubilant.all_active(status, "rabbitmq-server"),
        timeout=600,
    )
    amqp_host = juju.status().get_units("rabbitmq-server")["rabbitmq-server/0"].public_address
    logger.info("RabbitMQ address: " + amqp_host)

    # Useful to push arbitrary messages in test cases.
    juju.exec("sudo", "apt-get", "install", "-y", "amqp-tools", unit="rabbitmq-server/0")

    # Set up rabbitmq test user
    juju.exec("sudo", "rabbitmqctl", "add_user", "test", "test", unit="rabbitmq-server/0")
    juju.exec(
        "sudo",
        "rabbitmqctl",
        "set_user_tags",
        "test",
        "administrator",
        unit="rabbitmq-server/0",
    )
    juju.exec(
        "sudo",
        "rabbitmqctl",
        "set_permissions",
        "-p",
        "/",
        "test",
        "'.*'",
        "'.*'",
        "'.*'",
        unit="rabbitmq-server/0",
    )
    return {"host": amqp_host, "username": "test", "password": "test"}


@pytest.fixture
def error_tracker_config(amqp: dict[str, str], cassandra: dict[str, str]) -> str:
    return f"""
amqp_host = '{amqp["host"]}'
amqp_username = '{amqp["username"]}'
amqp_password = '{amqp["password"]}'
amqp_vhost = '/'

cassandra_keyspace = "crashdb"
cassandra_hosts = [ '{cassandra["host"]}' ]
cassandra_username = '{cassandra["username"]}'
cassandra_password = '{cassandra["password"]}'

os_auth_url = 'https://keystone.local:5000/v3'
os_username = 'admin'
os_password = '123456'
os_tenant_name = 'error-tracker_project'
os_region_name = 'default'

swift_bucket = "daisy-production-cores"
"""
