import logging

import jubilant
from conftest import charm_path

logger = logging.getLogger()


def test_deploy(
    juju: jubilant.Juju, amqp: dict[str, str], cassandra: dict[str, str], error_tracker_config: str
):
    juju.deploy(
        charm=charm_path("daisy"),
        app="daisy",
        config={"configuration": error_tracker_config},
    )

    juju.wait(lambda status: jubilant.all_active(status, "daisy"), timeout=600)

    # Check local config
    task = juju.exec("cat", "/home/ubuntu/config/local_config.py", unit="daisy/0")
    config = task.stdout
    assert f"amqp_host = '{amqp['host']}'" in config, (
        "missing or wrong amqp entries in configuration"
    )
    assert f"cassandra_hosts = [ '{cassandra['host']}' ]" in config, (
        "missing or wrong cassandra entry in configuration"
    )
    assert "swift_bucket = " in config, "missing swift entries in configuration"
