import json
import logging

import jubilant
from conftest import charm_path

logger = logging.getLogger()


def test_deploy(
    juju: jubilant.Juju, amqp: dict[str, str], cassandra: dict[str, str], error_tracker_config: str
):
    juju.deploy(
        charm=charm_path("timers"),
        app="timers",
        config={"configuration": error_tracker_config},
    )

    juju.wait(lambda status: jubilant.all_active(status, "timers"), timeout=600)

    # Check local config
    task = juju.exec("cat", "/home/ubuntu/config/local_config.py", unit="timers/0")
    config = task.stdout
    assert f"amqp_host = '{amqp['host']}'" in config, (
        "missing or wrong amqp entries in configuration"
    )
    assert f"cassandra_hosts = [ '{cassandra['host']}' ]" in config, (
        "missing or wrong cassandra entry in configuration"
    )
    assert "swift_bucket = " in config, "missing swift entries in configuration"

    # Check deployed systemd units
    task = juju.exec("systemctl", "list-units", "-o", "json", unit="timers/0")
    units = json.loads(task.stdout)
    et_units = [u for u in units if u["unit"].startswith("et-")]
    assert len(et_units) == 5, "wrong number of error tracker systemd units"
    assert all([u["active"] == "active" for u in et_units]), "not all systemd units are active"
