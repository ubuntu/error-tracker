import json
import logging

import jubilant
from utils import check_config

logger = logging.getLogger()


def test_deploy(
    juju: jubilant.Juju,
    amqp: dict[str, str],
    cassandra: dict[str, str],
    swift: dict[str, str],
    error_tracker_config: str,
    charm_path: str,
):
    juju.deploy(
        charm=charm_path,
        app="timers",
        config={
            "configuration": error_tracker_config,
            "enable_daisy": False,
            "enable_retracer": False,
            "enable_timers": True,
            "enable_web": False,
        },
    )

    juju.wait(lambda status: jubilant.all_active(status, "timers"), timeout=600)

    check_config(juju, amqp, cassandra, swift, "timers/0")

    # Check deployed systemd units
    task = juju.exec("systemctl", "list-units", "-o", "json", unit="timers/0")
    units = json.loads(task.stdout)
    et_units = [u for u in units if u["unit"].startswith("et-")]
    assert len(et_units) == 5, "wrong number of error tracker systemd units"
    assert all([u["active"] == "active" for u in et_units]), "not all systemd units are active"
