#!/usr/bin/env python3
# Copyright 2024 Skia
# See LICENSE file for licensing details.

"""Charm the retracer for Error Tracker."""

import logging
import ops

from pathlib import Path
from subprocess import check_call, CalledProcessError

logger = logging.getLogger(__name__)

REPO_LOCATION = Path("/home/ubuntu/error-tracker")


class RetracerCharm(ops.CharmBase):
    """Charm the application."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

    def _on_start(self, event: ops.StartEvent):
        """Handle start event."""
        self.unit.status = ops.ActiveStatus()

    def _on_install(self, event: ops.InstallEvent):
        """Handle install event."""
        try:
            self.unit.status = ops.MaintenanceStatus("Installing apt dependencies")
            check_call(["apt-get", "update", "-y"])
            check_call(
                [
                    "apt-get",
                    "install",
                    "-y",
                    "apport-retrace",
                    "git",
                    "python3-amqp",
                    "python3-cassandra",
                    "python3-pygit2",
                    "ubuntu-dbgsym-keyring",
                    "vim",
                ]
            )
        except CalledProcessError as e:
            logger.debug("Package install failed with return code %d", e.returncode)
            self.unit.status = ops.BlockedStatus("Failed installing apt packages.")
            return

        try:
            self.unit.status = ops.MaintenanceStatus("Installing retracer code")
            repo_url = self.config.get("repo-url")
            repo_branch = self.config.get("repo-branch")
            check_call(
                [
                    "sudo",
                    "-u",
                    "ubuntu",
                    "git",
                    "clone",
                    "-b",
                    repo_branch,
                    repo_url,
                    REPO_LOCATION,
                ]
            )
            self.unit.status = ops.ActiveStatus("Ready")
        except CalledProcessError as e:
            logger.debug(
                "Git clone of the code failed with return code %d", e.returncode
            )
            self.unit.status = ops.BlockedStatus("Failed git cloning the code.")
            return

    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        channel = self.config.get("channel")
        if channel in ["beta", "edge", "candidate", "stable"]:
            # os.system(f"snap refresh microsample --{channel}")
            workload_version = self._getWorkloadVersion()
            self.unit.set_workload_version(workload_version)
            self.unit.status = ops.ActiveStatus("Ready at '%s'" % channel)
        else:
            self.unit.status = ops.BlockedStatus("Invalid channel configured.")

    def _getWorkloadVersion(self):
        """Get the retracer version from the git repository"""
        workload_version = "retracer_v2"

        return workload_version


if __name__ == "__main__":  # pragma: nocover
    ops.main(RetracerCharm)  # type: ignore
