import logging
import shutil
from pathlib import Path
from subprocess import CalledProcessError, check_call, check_output

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


class ErrorTracker:
    def __init__(self):
        self.enable_retracer = True
        self.enable_timers = True
        self.enable_daisy = True
        self.enable_web = True
        self.daisy_port = 8000

    def install(self):
        self._install_deps()
        self._install_et()

    def _install_et(self):
        shutil.copytree(".", REPO_LOCATION)
        check_call(["chown", "-R", "ubuntu:ubuntu", str(REPO_LOCATION)])

    def get_version(self):
        """Get the retracer version"""
        try:
            version = check_output(
                [
                    "sudo",
                    "-u",
                    "ubuntu",
                    "python3",
                    "-c",
                    "import errortracker; print(errortracker.__version__)",
                ],
                cwd=REPO_LOCATION / "src",
            )
            return version.decode()
        except CalledProcessError as e:
            logger.error("Unable to get version (%d, %s)", e.returncode, e.stderr)
            return "unknown"

    def _install_deps(self):
        try:
            check_call(["apt-get", "update", "-y"])
            check_call(
                [
                    "apt-get",
                    "install",
                    "-y",
                    "git",
                    "python3-amqp",
                    "python3-apport",
                    "python3-apt",
                    "python3-bson",
                    "python3-cassandra",
                    "python3-flask",
                    "python3-swiftclient",
                ]
            )
        except CalledProcessError as e:
            logger.debug("Package install failed with return code %d", e.returncode)
            return

    def configure(self, config: str):
        config_location = REPO_LOCATION / "src"
        (config_location / "local_config.py").write_text(config)

    def configure_daisy(self):
        logger.info("Configuring daisy")
        logger.info("Installing additional daisy dependencies")
        check_call(["apt-get", "install", "-y", "gunicorn"])
        systemd_unit_location = Path("/") / "etc" / "systemd" / "system"
        systemd_unit_location.mkdir(parents=True, exist_ok=True)
        (systemd_unit_location / "daisy.service").write_text(
            f"""
[Unit]
Description=Daisy
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory={REPO_LOCATION}/src
ExecStart=gunicorn -c {REPO_LOCATION}/src/daisy/gunicorn_config.py 'daisy.app:create_app()'
Restart=always

[Install]
WantedBy=multi-user.target
"""
        )

        check_call(["systemctl", "daemon-reload"])

        logger.info("enabling systemd units")
        check_call(["systemctl", "enable", "daisy"])

        logger.info("restarting systemd units")
        check_call(["systemctl", "restart", "daisy"])

    def configure_retracer(self, retracer_failed_queue: bool):
        logger.info("Configuring retracer")
        failed = "--failed" if retracer_failed_queue else ""
        # Work around https://bugs.launchpad.net/ubuntu/+source/gdb/+bug/1818918
        # Apport will not be run as root, thus the included workaround here will hit ENOPERM
        (Path("/") / "usr" / "lib" / "debug" / ".dwz").mkdir(parents=True, exist_ok=True)
        logger.info("Installing additional retracer dependencies")
        check_call(
            [
                "apt-get",
                "install",
                "-y",
                "apport-retrace",
                "ubuntu-dbgsym-keyring",
            ]
        )

        logger.info("Configuring retracer systemd units")
        systemd_unit_location = Path("/") / "etc" / "systemd" / "system"
        systemd_unit_location.mkdir(parents=True, exist_ok=True)
        (systemd_unit_location / "retracer@.service").write_text(
            f"""
[Unit]
Description=Retracer

[Service]
User=ubuntu
Group=ubuntu
Environment=PYTHONPATH={REPO_LOCATION}/src
ExecStart=python3 {REPO_LOCATION}/src/retracer.py --config-dir {REPO_LOCATION}/src/retracer/config --sandbox-dir {HOME}/cache --cleanup-debs --cleanup-sandbox --architecture %i --core-storage {HOME}/var --verbose {failed}
Restart=on-failure

[Install]
WantedBy=multi-user.target
"""
        )

        check_call(["systemctl", "daemon-reload"])

        logger.info("enabling systemd units")
        check_call(["systemctl", "enable", "retracer@amd64"])
        check_call(["systemctl", "enable", "retracer@arm64"])
        check_call(["systemctl", "enable", "retracer@armhf"])
        check_call(["systemctl", "enable", "retracer@i386"])

        logger.info("restarting systemd units")
        check_call(["systemctl", "restart", "retracer@amd64"])
        check_call(["systemctl", "restart", "retracer@arm64"])
        check_call(["systemctl", "restart", "retracer@armhf"])
        check_call(["systemctl", "restart", "retracer@i386"])

    def configure_timers(self):
        logger.info("Configuring timers")
        setup_systemd_timer(
            "et-unique-users-daily-update",
            "Error Tracker - Unique users daily update",
            f"{REPO_LOCATION}/src/tools/unique_users_daily_update.py",
            "*-*-* 00:30:00",  # every day at 00:30
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
            "*-*-* 02:30:00",  # every day at 02:30
        )
        setup_systemd_timer(
            "et-swift-corrupt-core-check",
            "Error Tracker - Swift - Check for corrupt cores",
            f"{REPO_LOCATION}/src/tools/swift_corrupt_core_check.py",
            "*-*-* 04:30:00",  # every day at 04:30
        )
        setup_systemd_timer(
            "et-swift-handle-old-cores",
            "Error Tracker - Swift - Handle old cores",
            f"{REPO_LOCATION}/src/tools/swift_handle_old_cores.py",
            "*-*-* *:45:00",  # every hour at minute 45
        )

    def configure_web(self):
        logger.info("Configuring web")
