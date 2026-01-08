import configparser
import logging
import subprocess
from pathlib import Path
from typing import Generator

import jubilant
import pytest
from _pytest.config.argparsing import Parser

logger = logging.getLogger()


def pytest_addoption(parser: Parser):
    parser.addoption(
        "--charm-path",
        help="Pre-built charm file to deploy, rather than building from source",
    )


@pytest.fixture(scope="module")
def charm_path(request):
    charm_file = request.config.getoption("--charm-path")
    if charm_file:
        return charm_file

    charm_dir = Path(__file__).parent.parent.parent
    subprocess.run(
        ["/snap/bin/charmcraft", "pack", "--verbose", "--project-dir", charm_dir],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    return next(Path.glob(Path("."), "*.charm")).absolute()


@pytest.fixture(scope="module")
def juju() -> Generator[jubilant.Juju, None, None]:
    with jubilant.temp_model() as juju:
        yield juju


@pytest.fixture
def services(juju: jubilant.Juju) -> None:
    """
    This fixture is just an optimization to start all services at once and
    have them get installed in parallel. Don't use it directly and use each
    individual service instead.
    """
    juju.deploy(
        "cassandra",
        config={
            "install_keys": "7464AAD9068241C50BA6A26232F35CB2F546D93E",
            "install_sources": "deb https://debian.cassandra.apache.org 311x main",
        },
    )
    juju.deploy("rabbitmq-server")
    juju.deploy(charm="ubuntu", app="swift")


@pytest.fixture
def cassandra(juju: jubilant.Juju, services) -> dict[str, str]:
    juju.wait(
        lambda status: jubilant.all_active(status, "cassandra"),
        timeout=900,
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
def amqp(juju: jubilant.Juju, services) -> dict[str, str]:
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
def swift(juju: jubilant.Juju, services) -> dict[str, str]:
    juju.wait(
        lambda status: jubilant.all_active(status, "swift"),
        timeout=600,
    )
    swift_host = juju.status().get_units("swift")["swift/0"].public_address
    logger.info("swift address: " + swift_host)

    # juju.exec("sudo", "apt-get", "update", unit="swift/0")
    juju.exec("sudo", "apt-get", "install", "-Uy", "docker.io", unit="swift/0")
    juju.exec(
        "docker",
        "run",
        "--name",
        "swift",
        "--network",
        "host",
        "--rm",
        "-d",
        "docker.io/openstackswift/saio",
        unit="swift/0",
    )
    return {
        "auth_url": f"http://{swift_host}:8080/auth/v1.0",
        "username": "test:tester",
        "password": "testing",
        "auth_version": "1.0",
    }


@pytest.fixture
def error_tracker_config(
    amqp: dict[str, str], cassandra: dict[str, str], swift: dict[str, str]
) -> str:
    return f"""
amqp_creds = {{
    "host": "{amqp["host"]}",
    "username": "{amqp["username"]}",
    "password": "{amqp["password"]}",
}}

cassandra_creds = {{
    "keyspace": "crashdb",
    "hosts": [ "{cassandra["host"]}" ],
    "username": "{cassandra["username"]}",
    "password": "{cassandra["password"]}",
}}

swift_creds = {{
    "auth_url": "{swift["auth_url"]}",
    "username": "{swift["username"]}",
    "password": "{swift["password"]}",
    "auth_version": "{swift["auth_version"]}",
}}
"""
