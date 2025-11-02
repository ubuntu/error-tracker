import logging

import jubilant
from tenacity import Retrying, stop_after_attempt, wait_exponential
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
        app="retracer",
        config={
            "configuration": error_tracker_config,
            "enable_daisy": False,
            "enable_retracer": True,
            "enable_timers": False,
            "enable_web": False,
        },
    )

    juju.wait(lambda status: jubilant.all_active(status, "retracer"), timeout=600)

    check_config(juju, amqp, cassandra, swift, "retracer/0")

    # Check retracer processes
    task = juju.exec("ps", "aux", unit="retracer/0")
    processes = task.stdout.splitlines()
    retracer_processes = [p for p in processes if "src/retracer.py" in p]
    try:
        assert len(retracer_processes) == 4, "wrong number of retracers processes"
    except AssertionError as e:
        # dump one retracer log. It's likely that all fail in the same way.
        logger.warning(juju.exec("journalctl", "-u", "retracer@amd64", unit="retracer/0").stdout)
        raise e

    # Send an empty crash, to verify it gets processed, even though not really retraced
    juju.exec(
        "swift",
        "-A",
        swift["os_auth_url"],
        "-U",
        swift["os_username"],
        "-K",
        swift["os_password"],
        "upload",
        "--object-name",
        "00000000-1111-4222-3333-444444444444",
        "cores",
        "/etc/os-release",  # Obviously not a valid core, but the file exists and is not empty
        unit="retracer/0",
    )
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
    # Let give this test a few chances to succeed, as it can sometimes be a bit
    # slow to process the crash
    for attempt in Retrying(
        stop=stop_after_attempt(5),
        wait=wait_exponential(min=5, max=30),
        reraise=True,
    ):
        with attempt:
            # Verify that the retracer didn't Traceback and processed the sent crash
            task = juju.exec("journalctl", "-u", "retracer@amd64.service", unit="retracer/0")
            retracer_logs = task.stdout
            assert "Waiting for messages in `retrace_amd64`" in retracer_logs, (
                "retracer didn't reach waiting on amqp"
            )
            assert (
                "00000000-1111-4222-3333-444444444444:swift:Failed to decompress core: Error -3 while decompressing data: incorrect header check"
                in retracer_logs
            ), "retracer didn't try to decompress the core. Either `swift` or `amqp` is broken."
