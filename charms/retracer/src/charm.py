#!/usr/bin/env python3
# Copyright 2024 Skia
# See LICENSE file for licensing details.

"""Charm the retracer for Error Tracker."""

import logging
import ops

from pathlib import Path
from subprocess import check_call, check_output, CalledProcessError

logger = logging.getLogger(__name__)

HOME = Path("~ubuntu").expanduser()
REPO_LOCATION = HOME / "error-tracker"


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
                    "python3-swiftclient",
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
        config = self.config.get("configuration")

        config_location = HOME / "config"
        config_location.mkdir(parents=True, exist_ok=True)
        (config_location / "local_config.py").write_text(config)

        systemd_unit_location = Path("/") / "etc" / "systemd" / "system"
        systemd_unit_location.mkdir(parents=True, exist_ok=True)
        (systemd_unit_location / "retracer.service").write_text(
            f"""
[Unit]
Description=Retracer

[Service]
User=ubuntu
Group=ubuntu
Environment=PYTHONPATH={HOME}/config
ExecStart={HOME}/error-tracker/src/retracer.py --config-dir {HOME}/error-tracker/src/retracer/config --sandbox-dir {HOME}/cache --architecture amd64 --core-storage {HOME}/var --output {HOME}/retracer-amd64.log --verbose
Restart=on-failure

[Install]
WantedBy=multi-user.target
"""
        )

        check_call(["systemctl", "daemon-reload"])
        check_call(["systemctl", "enable", "--now", "retracer"])
        self.unit.set_workload_version(self._getWorkloadVersion())
        self.unit.status = ops.ActiveStatus("Ready")

    def _getWorkloadVersion(self):
        """Get the retracer version from the git repository"""
        try:
            version = check_output(
                [
                    "sudo",
                    "-u",
                    "ubuntu",
                    "git",
                    "-C",
                    REPO_LOCATION,
                    "describe",
                    "--tags",
                    "--always",
                    "--dirty",
                ]
            )
            return version.decode()
        except CalledProcessError as e:
            logger.debug(
                "Unable to get workload version (%d, %s)", e.returncode, e.stderr
            )
            self.unit.status = ops.BlockedStatus("Failed git describe.")


if __name__ == "__main__":  # pragma: nocover
    ops.main(RetracerCharm)  # type: ignore
