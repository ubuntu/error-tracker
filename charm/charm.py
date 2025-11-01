#!/usr/bin/env python3
# Copyright 2025 Skia
# See LICENSE file for licensing details.

"""Charm the Error Tracker."""

import logging

import ops
from charms.haproxy.v1.haproxy_route import HaproxyRouteRequirer

from errortracker import ErrorTracker

logger = logging.getLogger(__name__)


class ErrorTrackerCharm(ops.CharmBase):
    """Charm the application."""

    def __init__(self, *args):
        super().__init__(*args)
        self._error_tracker = ErrorTracker()
        self.route_daisy = HaproxyRouteRequirer(
            self,
            service="daisy",
            ports=[self._error_tracker.daisy_port],
            relation_name="route_daisy",
        )

        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

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
        enable_web = self.config.get("enable_web")

        config = self.config.get("configuration")

        self._error_tracker.configure(config)

        # TODO: the charms know how to enable components, but not disable them.
        # This is a bit annoying, but also doesn't have a very big impact in
        # practice. This charm has no configuration where it's supposed to store
        # data, so it's always very easy to remove a unit and recreate.
        if enable_daisy:
            self._error_tracker.configure_daisy()
            self.unit.set_ports(self._error_tracker.daisy_port)
        if enable_retracer:
            self._error_tracker.configure_retracer(self.config.get("retracer_failed_queue"))
        if enable_timers:
            self._error_tracker.configure_timers()
        if enable_web:
            self._error_tracker.configure_web()

        self.unit.set_workload_version(self._error_tracker.get_version())
        self.unit.status = ops.ActiveStatus("Ready")


if __name__ == "__main__":  # pragma: nocover
    ops.main(ErrorTrackerCharm)  # type: ignore
