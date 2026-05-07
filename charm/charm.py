#!/usr/bin/env python3
# Copyright 2025 Skia
# See LICENSE file for licensing details.

"""Charm the Error Tracker."""

import logging

import ops
from charms.haproxy.v1.haproxy_route import HaproxyRouteRequirer
from charms.traefik_k8s.v2.ingress import (
    IngressPerAppReadyEvent,
)
from charms.traefik_k8s.v2.ingress import (
    IngressPerAppRequirer as IngressRequirer,
)

from errortracker import ErrorTracker

logger = logging.getLogger(__name__)


class ErrorTrackerCharm(ops.CharmBase):
    """Charm the application."""

    def __init__(self, *args):
        super().__init__(*args)
        self._error_tracker = ErrorTracker()

        self.ingress_daisy = IngressRequirer(
            self,
            port=self._error_tracker.daisy_port,
            strip_prefix=True,
            relation_name="ingress_daisy",
        )
        self.ingress_errors = IngressRequirer(
            self,
            port=self._error_tracker.errors_port,
            strip_prefix=True,
            relation_name="ingress_errors",
        )

        self.route_daisy = HaproxyRouteRequirer(
            self,
            service="daisy",
            ports=[self._error_tracker.daisy_port],
            relation_name="route_daisy",
        )
        self.route_errors = HaproxyRouteRequirer(
            self,
            service="errors",
            ports=[self._error_tracker.errors_port],
            relation_name="route_errors",
        )

        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.upgrade_charm, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

        self.framework.observe(self.route_daisy.on.ready, self._on_endpoints_ready)
        self.framework.observe(self.route_errors.on.ready, self._on_endpoints_ready)

        self.framework.observe(self.ingress_daisy.on.ready, self._on_ingress_ready)
        self.framework.observe(self.ingress_errors.on.ready, self._on_ingress_ready)

    def _on_start(self, event: ops.StartEvent):
        """Handle start event."""
        self.unit.status = ops.ActiveStatus()

    def _on_install(self, event: ops.InstallEvent):
        """Handle install event."""
        self.unit.status = ops.MaintenanceStatus("Installing the error tracker")
        try:
            self._error_tracker.install()
        except Exception as e:
            logger.error("Failed to install the Error Tracker: %s", str(e))
            self.unit.status = ops.BlockedStatus("Failed installing the Error Tracker")
            return

        self.unit.status = ops.ActiveStatus("Ready")

    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        enable_daisy = self.config.get("enable_daisy")
        enable_retracer = self.config.get("enable_retracer")
        enable_timers = self.config.get("enable_timers")
        enable_errors = self.config.get("enable_errors")

        config = self.config.get("configuration")

        self._error_tracker.configure(config)

        # TODO: the charms know how to enable components, but not disable them.
        # This is a bit annoying, but also doesn't have a very big impact in
        # practice. This charm has no configuration where it's supposed to store
        # data, so it's always very easy to remove a unit and recreate.
        ports = []
        if enable_daisy:
            self._error_tracker.configure_daisy()
            ports.append(self._error_tracker.daisy_port)
        if enable_retracer:
            self._error_tracker.configure_retracer(self.config.get("retracer_failed_queue"))
        if enable_timers:
            self._error_tracker.configure_timers()
        if enable_errors:
            self._error_tracker.configure_errors()
            ports.append(self._error_tracker.errors_port)
        self.unit.set_ports(*ports)

        self.unit.set_workload_version(self._error_tracker.get_version())

        self.unit.status = ops.ActiveStatus("Ready")

    def _on_ingress_ready(self, event: IngressPerAppReadyEvent):
        logger.info("ingress URL: %s", event.url)
        daisy_hostname = self.config.get("daisy_hostname")
        errors_hostname = self.config.get("errors_hostname")
        enable_daisy = self.config.get("enable_daisy")
        enable_errors = self.config.get("enable_errors")
        if enable_daisy:
            self.ingress_daisy.provide_ingress_requirements(
                port=self._error_tracker.daisy_port,
                host=daisy_hostname,
            )
        if enable_errors:
            self.ingress_errors.provide_ingress_requirements(
                port=self._error_tracker.errors_port,
                host=errors_hostname,
            )

    def _on_endpoints_ready(self, event):
        daisy_hostname = self.config.get("daisy_hostname")
        errors_hostname = self.config.get("errors_hostname")
        enable_daisy = self.config.get("enable_daisy")
        enable_errors = self.config.get("enable_errors")
        if enable_daisy:
            self.route_daisy.provide_haproxy_route_requirements(
                service="daisy",
                ports=[self._error_tracker.daisy_port],
                hostname=daisy_hostname,
            )
        if enable_errors:
            self.route_errors.provide_haproxy_route_requirements(
                service="errors",
                ports=[self._error_tracker.errors_port],
                hostname=errors_hostname,
                header_rewrite_expressions=[
                    ("X-Forwarded-Proto", "https if { ssl_fc }"),
                    ("X-Forwarded-For", "%[src]"),
                ],
            )


if __name__ == "__main__":  # pragma: nocover
    ops.main(ErrorTrackerCharm)  # type: ignore
