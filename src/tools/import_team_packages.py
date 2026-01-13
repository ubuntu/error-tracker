#!/usr/bin/python3

from contextlib import suppress

import requests
from launchpadlib.errors import ResponseError
from launchpadlib.launchpad import Launchpad

from errortracker import cassandra

SRC_PACKAGE_TEAM_MAPPING = "https://ubuntu-archive-team.ubuntu.com/package-team-mapping.json"


cassandra.setup_cassandra()
session = cassandra.cassandra_session()

user_binary_packages_insert = session.prepare(
    f'INSERT INTO {session.keyspace}."UserBinaryPackages" (key, column1, value) VALUES (?, ?, 0x)'
)

launchpad = Launchpad.login_anonymously("unsubscribed-packages", "production")
ubuntu = launchpad.distributions["ubuntu"]
archive = ubuntu.getArchive(name="primary")


def get_binary_packages(src_pkg) -> set[str]:
    print(f" source: {src_pkg} ", end="")
    src = archive.getPublishedSources(
        source_name=src_pkg,
        exact_match=True,
        order_by_date=True,
        status="Published",
    )[0]
    bins = set()
    for bin_pkg in src.getPublishedBinaries(active_binaries_only=True):
        bins.add(bin_pkg.binary_package_name)
    print(f"binaries: {bins}")

    return bins


def import_user_binary_packages(team_name, src_pkgs):
    print(f"Fetching packages for {team_name}")
    for src_pkg in src_pkgs:
        with suppress(IndexError, ResponseError):
            binary_packages = get_binary_packages(src_pkg)
            for binary_package in binary_packages:
                session.execute(user_binary_packages_insert, [team_name, binary_package])


if __name__ == "__main__":
    print("Downloading package team mapping")
    mapping = requests.get(SRC_PACKAGE_TEAM_MAPPING).json()
    for team, packages in mapping.items():
        import_user_binary_packages(team, packages)
