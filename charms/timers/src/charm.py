#!/usr/bin/env python3
# Copyright 2025 Skia
# See LICENSE file for licensing details.

"""Charm the timers for Error Tracker."""

import logging
import ops

from pathlib import Path
from subprocess import check_call, check_output, CalledProcessError

logger = logging.getLogger(__name__)

HOME = Path("~ubuntu").expanduser()
REPO_LOCATION = HOME / "error-tracker"


def setup_systemd_timer(unit_name, description, command, calendar):
    systemd_unit_location = Path("/") / "etc" / "systemd" / "system"
    systemd_unit_location.mkdir(parents=True, exist_ok=True)

    (systemd_unit_location / f"{unit_name}.service").write_text(
        f"""
[Unit]
Description={description}

[Service]
Type=oneshot
User=ubuntu
Environment=PYTHONPATH={HOME}/config
ExecStart={command}
"""
    )
    (systemd_unit_location / f"{unit_name}.timer").write_text(
        f"""
[Unit]
Description={description}

[Timer]
OnCalendar={calendar}
Persistent=true

[Install]
WantedBy=timers.target
"""
    )

    check_call(["systemctl", "daemon-reload"])
    check_call(["systemctl", "enable", "--now", f"{unit_name}.timer"])


class TimersCharm(ops.CharmBase):
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
                    "python3-requests",
                    "python3-swiftclient",
                    "vim",
                ]
            )
        except CalledProcessError as e:
            logger.debug("Package install failed with return code %d", e.returncode)
            self.unit.status = ops.BlockedStatus("Failed installing apt packages.")
            return

        try:
            self.unit.status = ops.MaintenanceStatus("Installing error-tracker code")
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
        # Make sure the repo is up to date
        repo_url = self.config.get("repo-url")
        repo_branch = self.config.get("repo-branch")
        check_call(
            [
                "sudo",
                "-u",
                "ubuntu",
                "git",
                "-C",
                REPO_LOCATION,
                "fetch",
                "--update-head-ok",
                "--force",
                repo_url,
                f"refs/heads/{repo_branch}:refs/heads/{repo_branch}",
            ]
        )
        check_call(
            [
                "sudo",
                "-u",
                "ubuntu",
                "git",
                "-C",
                REPO_LOCATION,
                "reset",
                "--hard",
                repo_branch,
            ]
        )

        config = self.config.get("configuration")

        config_location = HOME / "config"
        config_location.mkdir(parents=True, exist_ok=True)
        (config_location / "local_config.py").write_text(config)

        setup_systemd_timer(
            "et-unique-users-daily-update",
            "Error Tracker - Unique users daily update",
            f"{REPO_LOCATION}/src/tools/unique_users_daily_update.py",
            "*-*-* 00:30:00",
        )
        setup_systemd_timer(
            "et-import-bugs",
            "Error Tracker - Import bugs",
            f"{REPO_LOCATION}/src/tools/import_bugs.py",
            "*-*-* 01,04,07,10,13,16,19,22:00:00",  # every three hours
        )
        setup_systemd_timer(
            "et-import-team-packages",
            "Error Tracker - Import team packages",
            f"{REPO_LOCATION}/src/tools/import_team_packages.py",
            "*-*-* 02:30:00",
        )
        self.unit.set_workload_version(self._getWorkloadVersion())
        self.unit.status = ops.ActiveStatus("Ready")

    def _getWorkloadVersion(self):
        """Get the error tracker version from the git repository"""
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
    ops.main(TimersCharm)  # type: ignore
