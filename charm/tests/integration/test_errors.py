import logging

import jubilant
from requests import Session
from tenacity import Retrying, stop_after_attempt, wait_exponential
from utils import DNSResolverHTTPSAdapter, check_config

logger = logging.getLogger()

HAPROXY = "haproxy"
SSC = "self-signed-certificates"

external_hostname = "errors.internal"


def test_deploy(
    juju: jubilant.Juju,
    amqp: dict[str, str],
    cassandra: dict[str, str],
    swift: dict[str, str],
    error_tracker_config: str,
    charm_path: str,
):
    """
    Deploy everything at once, but don't integrate anything. This is just to
    speed up CI by parallelizing deployment.
    """
    juju.deploy(
        charm=charm_path,
        app="errors",
        config={
            "configuration": error_tracker_config,
            "errors_hostname": external_hostname,
            "enable_daisy": False,
            "enable_retracer": False,
            "enable_timers": False,
            "enable_errors": True,
        },
    )
    juju.deploy(HAPROXY, channel="2.8/edge", config={"external-hostname": "haproxy.internal"})
    juju.deploy(SSC, channel="1/edge")

    juju.wait(lambda status: jubilant.all_active(status, "errors"), timeout=600)

    check_config(juju, amqp, cassandra, swift, "errors/0")


def test_http(juju: jubilant.Juju):
    juju.integrate(HAPROXY + ":certificates", SSC + ":certificates")
    juju.integrate("errors:route_errors", HAPROXY)
    juju.wait(lambda status: jubilant.all_active(status, HAPROXY, SSC), timeout=1800)

    haproxy_ip = juju.status().apps[HAPROXY].units[f"{HAPROXY}/0"].public_address

    session = Session()
    session.mount("https://", DNSResolverHTTPSAdapter(external_hostname, haproxy_ip))

    # Let give this test a few chances to succeed, as it can sometimes be a bit
    # early and hit 503
    for attempt in Retrying(
        stop=stop_after_attempt(10),
        wait=wait_exponential(min=5, max=30),
        reraise=True,
    ):
        with attempt:
            response = session.get(
                f"https://{haproxy_ip}/",
                headers={"Host": external_hostname},
                verify=False,
                timeout=30,
            )
            assert response.status_code == 200
            assert "We collect hundreds of thousands of error reports daily" in response.text
