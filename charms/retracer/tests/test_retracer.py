import logging
import time

import jubilant
from conftest import charm_path

logger = logging.getLogger()


def test_deploy(
    juju: jubilant.Juju, amqp: dict[str, str], cassandra: dict[str, str], error_tracker_config: str
):
    juju.deploy(
        charm=charm_path("retracer"),
        app="retracer",
        config={"configuration": error_tracker_config},
    )

    juju.wait(lambda status: jubilant.all_active(status, "retracer"), timeout=600)

    # Check local config
    task = juju.exec("cat", "/home/ubuntu/config/local_config.py", unit="retracer/0")
    config = task.stdout
    assert f"amqp_host = '{amqp['host']}'" in config, (
        "missing or wrong amqp entries in configuration"
    )
    assert f"cassandra_hosts = [ '{cassandra['host']}' ]" in config, (
        "missing or wrong cassandra entry in configuration"
    )
    assert "swift_bucket = " in config, "missing swift entries in configuration"

    # Check retracer processes
    task = juju.exec("ps", "aux", unit="retracer/0")
    processes = task.stdout.splitlines()
    retracer_processes = [p for p in processes if "src/retracer.py" in p]
    assert len(retracer_processes) == 4, "wrong number of retracers processes"

    # Send an empty crash, to verify it gets processed, even though not really retraced
    juju.exec(
        "amqp-publish",
        "--server",
        amqp["host"],
        "--username",
        amqp["username"],
        "--password",
        amqp["password"],
        "-r",
        "retrace_amd64",
        "-b",
        "00000000-1111-4222-3333-444444444444:swift",
        unit="rabbitmq-server/0",
    )
    # Give some arbitrary time to process.
    # For now I'm taking that cursed path, and depending on how flaky this
    # becomes, I'll see later to implement a wait loop.
    time.sleep(4)

    # Verify that the retracer didn't Traceback and processed the sent crash
    task = juju.exec("journalctl", "-u", "retracer@amd64.service", unit="retracer/0")
    retracer_logs = task.stdout
    assert "Waiting for messages in `retrace_amd64`" in retracer_logs, (
        "retracer didn't reach waiting on amqp"
    )
    assert "Ack'ing message about old missing core." in retracer_logs, (
        "retracer didn't ack the OOPS retracing request"
    )
    assert (
        "Could not remove from the retracing row (00000000-1111-4222-3333-444444444444) (DoesNotExist())"
        in retracer_logs
    ), "retracer didn't try to remove the OOPS retracing request"
