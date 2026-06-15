#!/usr/bin/python3
"""Smoke-test wrapper around errortracker.launchpad.

Every public function of ``errortracker.launchpad`` is called explicitly with
some hand-picked arbitrary arguments, and its return value is printed so you
can eyeball whether it looks right. The point is to be able to run this again
and again against either version of ``launchpad.py`` and compare the output.

Run from the ``src`` directory (or with ``src`` on PYTHONPATH) so that the
``errortracker`` package is importable, the same as the other tools:

    cd src
    python3 tools/launchpad_tester.py

By default the bug-mutating functions (``create_bug`` and ``subscribe_user``)
are NOT exercised, to avoid creating real bugs / subscriptions. Pass
``--write`` to include them.
"""

import sys
import traceback

from errortracker import launchpad


def check(func, *args, **kwargs):
    """Call ``func`` with the given args and print what it returns."""
    call = ", ".join(
        [repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()]
    )
    print(f"\n{func.__name__}({call})")
    try:
        result = func(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - this is a debugging aid
        print(f"  raised {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return
    print(f"  -> ({type(result).__name__}) {result!r}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    include_write = "--write" in argv

    # Codename / version helpers.
    check(launchpad.get_all_codenames)
    check(launchpad.get_devel_series_codename)
    check(launchpad.get_codename_for_version, "24.04")
    check(launchpad.get_codename_for_version, "Ubuntu 22.04")
    check(launchpad.get_codename_for_version, "noble")
    check(launchpad.get_codename_for_version, "does-not-exist")
    check(launchpad.get_version_for_codename, "noble")
    check(launchpad.get_version_for_codename, "does-not-exist")

    # Binary package lookups.
    check(launchpad.get_versions_for_binary, "bash", "24.04")
    check(launchpad.get_versions_for_binary, "bash", None)
    check(launchpad.get_release_for_binary, "bash", "5.2.21-2ubuntu4")
    check(launchpad.binary_is_most_recent, "bash", "5.2.21-2ubuntu4")
    check(
        launchpad.binaries_are_most_recent,
        [("bash", "5.2.21-2ubuntu4"), ("coreutils", "9.4-2ubuntu1")],
    )
    check(
        launchpad.pocket_for_binaries,
        [("bash", "5.2.21-2ubuntu4", "Ubuntu 24.04")],
    )

    # Source package lookups.
    check(launchpad.is_source_package, "bash")
    check(launchpad.is_source_package, "this-is-not-a-package")
    check(launchpad.get_binaries_in_source_package, "bash")
    check(launchpad.get_binaries_in_source_package, "bash", "24.04")
    check(launchpad.is_valid_source_version, "bash", "5.2.21-2ubuntu4")
    check(
        launchpad.get_pocket_for_source_version,
        "bash",
        "5.2.21-2ubuntu4",
        "Ubuntu 24.04",
    )

    # Bug lookups.
    check(launchpad.bug_is_fixed, "1")
    check(launchpad.bug_is_fixed, "1", "Ubuntu 24.04")
    check(launchpad.bug_get_master_id, "1")

    # People / packageset lookups.
    check(launchpad.get_subscribed_packages, "ubuntu-core-dev")
    check(launchpad.get_packages_in_packageset_name, "24.04", "core")

    if include_write:
        # These have side effects (they create a bug / a subscription), so
        # they are only run when explicitly requested with --write.
        check(
            launchpad.create_bug,
            "test signature from launchpad_tester",
            source="bash",
            releases=["Ubuntu 24.04"],
        )
        check(launchpad.subscribe_user, "1", "ubuntu-core-dev")
    else:
        print("\nSkipping create_bug / subscribe_user (pass --write to run them).")


if __name__ == "__main__":
    main()
